"""`snapdec bench` — fixed mini suite against the active (or mock) backend.

Measures what AGENTS.md allows claims to be made from: accuracy on a
labeled mini-suite, calibration (Brier on yes/no checks), and latency.
Latency is measured direct-to-backend (no daemon hop) and the output says
so. Committed runs live in docs/benchmarks/ — mock runs are harness
self-tests, not model-quality claims.
"""

from __future__ import annotations

import statistics
import time
from typing import Any

from ._brand import __version__
from .decisions import policy as decision_policy
from .decisions.envelope import SystemOneRequest

SUITE_ID = "mini-v1"

_CI_CLASSES = {
    "infra": "network, runner, or environment problem",
    "bug": "real code bug (assertion, logic, crash)",
    "deps": "missing or wrong dependency",
    "timeout": "test exceeded its time budget",
}
_CI_ITEMS = [  # (id, text, ground truth)
    ("c1", "OSError: network unreachable while fetching wheels on runner 7", "infra"),
    ("c2", "AssertionError: expected status 200, got 500", "bug"),
    ("c3", "ModuleNotFoundError: No module named 'requests'", "deps"),
    ("c4", "ConnectionResetError: read timed out talking to postgres-test", "infra"),
    ("c5", "TypeError: none of the output files were produced by build step", "bug"),
    ("c6", "pip resolver backtracking for 15 minutes, then exit code 1", "deps"),
]
_CHECK_ITEMS = [  # (id, evidence+question, truth as 0/1)
    ("k1", "git log shows commit 4f2a titled 'fix: handle empty payload'; "
           "question: does this commit touch error handling?", 1),
    ("k2", "README says 'run make test'; question: does the README document "
           "a deployment step?", 0),
    ("k3", "stack trace ends in ssl.SSLError during artifact upload; "
           "question: is the failure network-related?", 1),
    ("k4", "changelog entry mentions 'performance'; question: does this "
           "release fix a security vulnerability?", 0),
]
_SCORE_LEVELS = ["trivial", "minor", "major", "critical"]
_SCORE_ITEMS = [  # (id, text, expected nearest level)
    ("s1", "typo in a log message", "trivial"),
    ("s2", "race condition corrupts user data on save", "critical"),
]


def _nearest(ans, levels: list[str]) -> str:
    if ans.nearest_level in levels:
        return ans.nearest_level
    idx = max(0, min(len(levels) - 1, int(ans.score or 1) - 1))
    return levels[idx]


def run_bench(backend: Any) -> dict[str, Any]:
    """Run the fixed mini-suite sequentially; deterministic scoring."""
    latencies: list[float] = []
    rows: list[dict[str, Any]] = []

    def call(req: SystemOneRequest) -> Any:
        t0 = time.perf_counter()
        resp = backend.system_one(req)
        latencies.append((time.perf_counter() - t0) * 1000)
        return resp.answers

    for iid, text, truth in _CI_ITEMS:
        a = call(SystemOneRequest(
            state=text,
            questions={"cls": {"type": "choice",
                               "instructions": "Pick the best class for the text.",
                               "criteria": _CI_CLASSES}}))["cls"]
        probs = a.probabilities or {}
        row = {"id": iid, "task": "classify", "predicted": a.choice,
               "truth": truth, "correct": a.choice == truth,
               "probabilities": probs}
        rows.append(decision_policy.apply_decision(row))

    brier: list[float] = []
    for iid, text, truth in _CHECK_ITEMS:
        ev, q = text.rsplit(" question: ", 1)
        a = call(SystemOneRequest(
            state=ev, questions={"k": {"type": "noul", "instructions": q}}))["k"]
        p = a.p_yes if a.p_yes is not None else 0.0
        brier.append((p - truth) ** 2)
        probs = a.probabilities or {"yes": p, "no": 1.0 - p}
        row = {"id": iid, "task": "check", "p_yes": round(p, 4),
               "truth": bool(truth), "correct": (p > 0.5) == bool(truth),
               "probabilities": probs}
        rows.append(decision_policy.apply_decision(row))

    for iid, text, truth in _SCORE_ITEMS:
        a = call(SystemOneRequest(
            state=text,
            questions={"sev": {"type": "score",
                               "instructions": "Rate severity on the given scale.",
                               "criteria": _SCORE_LEVELS}}))["sev"]
        got = _nearest(a, _SCORE_LEVELS)
        row = {"id": iid, "task": "score", "predicted": got, "truth": truth,
               "correct": got == truth,
               "probabilities": a.probabilities or {}}
        rows.append(decision_policy.apply_decision(row))

    def acc(task: str) -> float:
        subset = [r for r in rows if r["task"] == task]
        return round(sum(r["correct"] for r in subset) / len(subset), 4)

    lat_sorted = sorted(latencies)
    p95 = lat_sorted[min(len(lat_sorted) - 1, round(0.95 * (len(lat_sorted) - 1)))]
    desc = backend.describe()
    return {
        "suite": SUITE_ID,
        "snapdec_version": __version__,
        "backend": {"name": desc.get("name"), "model": desc.get("model")},
        "items": len(rows),
        "classify_accuracy": acc("classify"),
        "check_accuracy": acc("check"),
        "check_brier": round(statistics.fmean(brier), 4),
        "score_exact": acc("score"),
        "decision_mix": {
            "auto": sum(1 for r in rows if r["decision"] == "auto"),
            "review": sum(1 for r in rows if r["decision"] != "auto"),
        },
        "latency_p50_ms": round(statistics.median(latencies), 2),
        "latency_p95_ms": round(p95, 2),
        "latency_note": "direct-to-backend (no daemon hop)",
        "results": rows,
    }
