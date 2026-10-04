"""MCP shim (`snapdec mcp`) — what agents launch (§7).

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

from .._brand import NAME, __version__
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


def _model_label() -> str:
    try:
        from .. import config as _cfg

        cfg = _cfg.Config.load()
        return cfg.model or cfg.backend or "default"
    except Exception:
        return "default"


def _add_status(env: dict[str, Any], state_chars: int) -> dict[str, Any]:
    """One quiet footer line after every Tier-1 answer: what ran, how fast,
    how much text stayed off the host model. Rendered by the agent as part
    of the tool result — informational, never parsed."""
    s = env.get("summary") or {}
    env["status"] = (f"· snapdec {__version__} · {_model_label()} · "
                     f"{(env.get('backend') or {}).get('latency_ms', '?')} ms · "
                     f"{s.get('auto', 0)}/{s.get('items', 0)} auto · "
                     f"~{state_chars // 4} tok offloaded")
    return env


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
                                    raw.get("snapdec_note", ""))
        answers = raw.get("answers") or {}
        results = []
        for name, a in answers.items():
            probs = a.get("probabilities") or {}
            p_yes: float | None = None
            row: dict[str, Any] = {"id": name}
            if a.get("type") == "noul":
                # wire may encode bool or P(yes) float (laya) — normalize
                p = a.get("noul")
                p_yes = (1.0 if p else 0.0) if isinstance(p, bool) else float(p or 0.0)
                row["verdict"] = "yes" if p_yes > 0.5 else "no"
                row["p_yes"] = round(p_yes, 4)
            elif a.get("type") == "choice":
                row["label"] = a.get("choice")
            elif a.get("type") == "score":
                row["score"] = a.get("score")
                row["nearest_level"] = a.get("nearest_level")
            row["probabilities"] = probs or (
                {"yes": p_yes, "no": 1.0 - p_yes}
                if a.get("type") == "noul" and p_yes is not None else {})
            results.append(decision_policy.apply_decision(row))
        latency = round((time.perf_counter() - started) * 1000, 1)
        info = _backend_info()
        info["latency_ms"] = latency
        env = make_envelope(results, backend=info)
        return _add_status(env, len(str(payload.get("state", ""))))
    except ConnectionError as e:
        return failure_envelope("no_backend", str(e))
    except Exception as e:  # noqa: BLE001 — never raise into the host agent
        return failure_envelope("error", f"{type(e).__name__}: {e}")


def _tier1_many(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Fan-out (§4.6): one request per item so each item is its own state —
    small-context backends can't answer N items against one shared blob.
    Runs in parallel; results keep input order; latency = slowest call."""
    import concurrent.futures as cf

    t0 = time.perf_counter()
    envs = []
    with cf.ThreadPoolExecutor(max_workers=min(8, len(payloads) or 1)) as ex:
        for env in ex.map(_tier1, payloads):
            envs.append(env)
    results = [r for env in envs for r in env.get("results", [])]
    if not results and envs:
        return envs[0]  # preserve the failure envelope shape
    info = _backend_info()
    info["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    chars = sum(len(str(p.get("state", ""))) for p in payloads)
    return _add_status(make_envelope(results, backend=info), chars)


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
        # laya (and the wire contract) require non-empty instructions
        instructions = instructions or \
            "Pick the single best-fitting class for the text."
        payloads = [{
            "state": str(it.get("text", "")),
            "questions": {"item": {"type": "choice",
                                   "instructions": instructions,
                                   "criteria": classes}},
        } for it in items]
        env = _tier1_many(payloads)
        for it, r in zip(items, env.get("results", []), strict=False):
            r["id"] = it.get("id", r.get("id"))
        return env

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
        payloads = [{
            "state": str(it.get("text", "")),
            "questions": {"item": {"type": "score",
                                   "instructions":
                                       "Rate the item on the given scale.",
                                   "criteria": levels}},
        } for it in items]
        env = _tier1_many(payloads)
        for it, r in zip(items, env.get("results", []), strict=False):
            r["id"] = it.get("id", r.get("id"))
        return env

    @server.tool(name="rank", description=(
        "Rank candidates by relevance to a query. Input: query, "
        "candidates[{id,text}], optional top_k. Returns sorted relevance."
    ))
    def rank(query: str, candidates: list[dict[str, Any]],
             top_k: int = 10) -> dict[str, Any]:
        candidates = candidates[:MAX_ITEMS_PER_CALL]
        payloads = [{
            "state": str(c.get("text", "")),
            "questions": {"item": {"type": "noul",
                                   "instructions":
                                       f"Is this relevant to: {query}? "
                                       "Answer yes or no."}},
        } for c in candidates]
        env = _tier1_many(payloads)
        for c, r in zip(candidates, env.get("results", []), strict=False):
            r["id"] = c.get("id", r.get("id"))
        ranked = sorted(env.get("results", []),
                        key=lambda r: r.get("probability", 0), reverse=True)
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
        sys.stderr.write("snapdec mcp: stopped\n")


# allow `python -m snapdec.mcp.server`
if __name__ == "__main__":
    main()
