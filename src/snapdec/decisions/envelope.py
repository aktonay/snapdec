"""Canonical types — kept identical to the System One wire contract (§4.5).

Wire contract (POST /v1/systemone):
  SystemOneRequest { model?, state, questions: {name: Question} }
  Question  { type: choice|noul|score, instructions, criteria? }
  SystemOneResponse { answers: {name: Answer}, usage?, model? }

Decision envelope (§7.2) is what MCP tools return: every Tier-1 response
carries calibrated probabilities and an `auto | review` decision, and the
failure shape NEVER raises into the host agent (NFR-4, fail-closed).
"""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

QuestionType = Literal["choice", "noul", "score"]


class Question(BaseModel):
    type: QuestionType
    instructions: str = ""
    criteria: dict[str, str] | list[str] | None = None  # option→desc, or 2..10 levels


class Answer(BaseModel):
    type: QuestionType
    choice: str | None = None
    noul: bool | float | None = None  # servers send P(yes) as float; bool also OK
    score: float | None = None
    probabilities: dict[str, float] | None = None
    confidence: float | None = None
    nearest_level: str | None = None

    @property
    def p_yes(self) -> float | None:
        """Normalized P(yes) for noul answers regardless of wire encoding."""
        if self.noul is None:
            return None
        if isinstance(self.noul, bool):
            return 1.0 if self.noul else 0.0
        return float(self.noul)


class SystemOneRequest(BaseModel):
    model: str | None = None
    state: str | Any = ""
    questions: dict[str, Question] = Field(default_factory=dict)


class SystemOneResponse(BaseModel):
    answers: dict[str, Answer] = Field(default_factory=dict)
    usage: dict[str, Any] | None = None
    model: str | None = None


# ---------------------------------------------------------------- envelope

DEFAULT_POLICY = {"auto_accept": 0.85, "min_margin": 0.5, "calibrated": False}


def make_envelope(
    results: list[dict[str, Any]],
    *,
    backend: dict[str, Any],
    policy: dict[str, Any] | None = None,
    truncated: bool = False,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build the Tier-1 decision envelope every tool returns (§7.2)."""
    auto = sum(1 for r in results if r.get("decision") == "auto")
    return {
        "results": results,
        "summary": {"items": len(results), "auto": auto, "review": len(results) - auto},
        "policy": policy or DEFAULT_POLICY,
        "backend": backend,
        "truncated": truncated,
        "warnings": warnings or [],
    }


def failure_envelope(reason: str, hint: str = "") -> dict[str, Any]:
    """Fail-closed shape — the only alternative to a real answer (NFR-4)."""
    return {
        "results": [],
        "summary": {"items": 0, "auto": 0, "review": 0},
        "policy": DEFAULT_POLICY,
        "backend": {"name": "none", "ready": False},
        "truncated": False,
        "warnings": [],
        "decision": "review",
        "reason": reason,
        "hint": hint,
        "ts": time.time(),
    }


def add_status(env: dict[str, Any], state_chars: int, model: str,
               version: str) -> dict[str, Any]:
    """Quiet footer on every Tier-1 answer (ADR-0009): what ran, how fast,
    how much text stayed off the host model. Informational only."""
    s = env.get("summary") or {}
    env["status"] = (f"· snapdec {version} · {model} · "
                     f"{(env.get('backend') or {}).get('latency_ms', '?')} ms · "
                     f"{s.get('auto', 0)}/{s.get('items', 0)} auto · "
                     f"~{state_chars // 4} tok offloaded")
    return env
