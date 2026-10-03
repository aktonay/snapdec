"""Decision policy (§4.7): auto only when confident AND decisive AND clean.

`auto` iff probability ≥ auto_accept AND margin ≥ min_margin AND not
truncated AND backend healthy. Safety-class questions use asymmetric
thresholds (biased toward review) — they must never authorize anything.
"""

from __future__ import annotations

from typing import Any

SAFETY_BONUS = 0.05  # added to both thresholds for safety-class questions


def decide(
    probabilities: dict[str, float],
    *,
    auto_accept: float = 0.85,
    min_margin: float = 0.5,
    truncated: bool = False,
    safety: bool = False,
    backend_ready: bool = True,
) -> tuple[str, float, float]:
    """Return (decision, top_probability, margin)."""
    if not probabilities or truncated or not backend_ready:
        return "review", max(probabilities.values()) if probabilities else 0.0, 0.0
    if safety:
        auto_accept += SAFETY_BONUS
        min_margin = min(1.0, min_margin + SAFETY_BONUS)
    ranked = sorted(probabilities.values(), reverse=True)
    top = ranked[0]
    margin = top - (ranked[1] if len(ranked) > 1 else 0.0)
    ok = top >= auto_accept and margin >= min_margin
    return ("auto" if ok else "review"), top, margin


def apply_decision(result: dict[str, Any], *, safety: bool = False,
                   policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Decorate one result row with decision/probability/margin fields."""
    pol = policy or {}
    decision, top, margin = decide(
        result.get("probabilities") or {},
        auto_accept=pol.get("auto_accept", 0.85),
        min_margin=pol.get("min_margin", 0.5),
        truncated=bool(result.get("truncated", False)),
        safety=safety,
    )
    result.setdefault("probability", top)
    result.setdefault("margin", margin)
    result["decision"] = decision
    return result
