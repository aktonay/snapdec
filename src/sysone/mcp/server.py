"""MCP shim (`sysone mcp`) — what agents launch (§7).

Rules honored here:
- ≤ 6 tools, terse descriptions (host agents pay context per turn)
- starts in < 1 s (no heavy imports; daemon connection is per-call)
- stdout carries ONLY protocol (MCPServer handles that; log to stderr)
- every Tier-1 call is fail-closed: errors become review envelopes (NFR-4)
- MCP v2 SDK (`MCPServer`, spec 2026-07-28: no server→client calls)
"""

from __future__ import annotations

import sys
import time
from typing import Any

from .._brand import NAME
from ..decisions import policy as decision_policy
from ..decisions.envelope import failure_envelope, make_envelope
from ..decisions.tier0 import project_facts as _project_facts
from ..runtime import ipc
from ..runtime.lifecycle import warm_daemon

MAX_ITEMS_PER_CALL = 200


def _backend_info() -> dict[str, Any]:
    try:
        st = ipc.read_state() or {}
        return {"name": "daemon", "transport": st.get("transport"), "ready": True}
    except Exception:
        return {"name": "daemon", "ready": False}


_daemon_started = False


def _tier1(payload: dict[str, Any]) -> dict[str, Any]:
    """One fail-closed round trip to the daemon for Tier-1 decisions."""
    global _daemon_started
    started = time.perf_counter()
    try:
        if not _daemon_started:  # lazy start on first call (§4.4)
            _daemon_started = True
            warm_daemon()
        raw = ipc.call_systemone(payload)
        if raw.get("error") or raw.get("reason"):
            return failure_envelope(raw.get("reason", "error"),
                                    raw.get("sysone_note", ""))
        answers = raw.get("answers") or {}
        results = []
        for name, a in answers.items():
            probs = a.get("probabilities") or {}
            row: dict[str, Any] = {"id": name}
            if a.get("type") == "noul":
                row["verdict"] = "yes" if a.get("noul") else "no"
            elif a.get("type") == "choice":
                row["label"] = a.get("choice")
            elif a.get("type") == "score":
                row["score"] = a.get("score")
                row["nearest_level"] = a.get("nearest_level")
            row["probabilities"] = probs
            results.append(decision_policy.apply_decision(row))
        latency = round((time.perf_counter() - started) * 1000, 1)
        info = _backend_info()
        info["latency_ms"] = latency
        return make_envelope(results, backend=info)
    except ConnectionError as e:
        return failure_envelope("no_backend", str(e))
    except Exception as e:  # noqa: BLE001 — never raise into the host agent
        return failure_envelope("error", f"{type(e).__name__}: {e}")


def build_server() -> Any:
    from mcp.server.mcpserver import MCPServer

    server = MCPServer(
        name=NAME,
        instructions=(
            "Local decision tools: project_facts (deterministic repo facts) "
            "and classify/check/score/rank (calibrated typed decisions with "
            "auto|review). Advisory only — never use for security approvals."
        ),
    )

    @server.tool(name="project_facts", description=(
        "Detect a repo's test/lint/typecheck/build commands, package manager, "
        "monorepo layout, CI provider. Deterministic, no model. Input: path."
    ))
    def project_facts(path: str) -> dict[str, Any]:
        return _project_facts(path)

    @server.tool(name="classify", description=(
        "Label each item with one caller-defined class. Input: items[{id,text}], "
        "classes{label:description}, optional instructions. Returns probabilities."
    ))
    def classify(items: list[dict[str, Any]], classes: dict[str, str],
                 instructions: str = "") -> dict[str, Any]:
        items = items[:MAX_ITEMS_PER_CALL]
        questions = {
            it.get("id", f"i{n}"): {
                "type": "choice", "instructions": instructions,
                "criteria": classes,
            }
            for n, it in enumerate(items)
        }
        state = "\n".join(str(i.get("text", "")) for i in items)
        return _tier1({"state": state, "questions": questions})

    @server.tool(name="check", description=(
        "Yes/no questions about one piece of evidence. Input: evidence, "
        "checks{name:question}. Returns verdict yes|no|uncertain per check."
    ))
    def check(evidence: str, checks: dict[str, str]) -> dict[str, Any]:
        questions = {k: {"type": "noul", "instructions": v} for k, v in checks.items()}
        env = _tier1({"state": evidence, "questions": questions})
        for r in env.get("results", []):
            if r.get("verdict") in ("yes", "no") and r.get("decision") != "auto":
                r["verdict"] = "uncertain"
        return env

    @server.tool(name="score", description=(
        "Ordinal rating per item (severity/priority/risk). Input: items[{id,text}], "
        "levels[2..10] low→high descriptions. Returns score + nearest_level."
    ))
    def score(items: list[dict[str, Any]], levels: list[str]) -> dict[str, Any]:
        if not 2 <= len(levels) <= 10:
            return failure_envelope("error", "levels must have 2..10 entries")
        items = items[:MAX_ITEMS_PER_CALL]
        questions = {
            it.get("id", f"i{n}"): {"type": "score", "criteria": levels}
            for n, it in enumerate(items)
        }
        state = "\n".join(str(i.get("text", "")) for i in items)
        return _tier1({"state": state, "questions": questions})

    @server.tool(name="rank", description=(
        "Rank candidates by relevance to a query. Input: query, "
        "candidates[{id,text}], optional top_k. Returns sorted relevance."
    ))
    def rank(query: str, candidates: list[dict[str, Any]],
             top_k: int = 10) -> dict[str, Any]:
        candidates = candidates[:MAX_ITEMS_PER_CALL]
        questions = {
            c.get("id", f"c{n}"): {"type": "noul",
                                   "instructions": f"Relevant to: {query}"}
            for n, c in enumerate(candidates)
        }
        state = query + "\n" + "\n".join(
            f"[{c.get('id', '')}] {c.get('text', '')}" for c in candidates)
        env = _tier1({"state": state, "questions": questions})
        results = env.get("results", [])
        ranked = sorted(results, key=lambda r: r.get("probability", 0), reverse=True)
        env["results"] = ranked[:top_k]
        env["any_relevant"] = bool(ranked) and ranked[0].get("probability", 0) > 0.5
        return env

    @server.tool(name="ask", description=(
        "Raw System One passthrough: mixed typed questions over one state. "
        "Input: state, questions{name:{type,instructions,criteria}}."
    ))
    def ask(state: str, questions: dict[str, Any]) -> dict[str, Any]:
        return _tier1({"state": state, "questions": questions})

    return server


def main() -> None:
    server = build_server()
    # stdout purity: MCPServer owns stdout; route our logging to stderr.
    try:
        server.run("stdio")
    except KeyboardInterrupt:
        pass
    finally:
        sys.stderr.write("sysone mcp: stopped\n")


# allow `python -m sysone.mcp.server`
if __name__ == "__main__":
    main()
