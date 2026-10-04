"""Auto-detect the provider from a pasted API key (§9.1 'all auto').

Only System One-compatible endpoints are usable by the remote backend.
OpenRouter is the universal bridge (serves typesafe/jev-router); OpenAI/
Groq/Anthropic keys do NOT speak /v1/systemone and are reported as such
with a hint instead of being silently misrouted.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderGuess:
    provider: str          # openrouter | typesafe | unsupported:<id> | unknown
    url: str = ""
    default_models: tuple[str, ...] = ()
    note: str = ""


_OPENROUTER = ProviderGuess(
    "openrouter", "https://openrouter.ai/api/v1",
    # kev-* ids were delisted from OpenRouter (verified 2026-10-04);
    # typesafe/jev-router is the only System One model served there.
    ("typesafe/jev-router",),
    "OpenRouter — hosts typesafe/jev-router · Jev DI 54.0 (breadth-v1)",
)
_TYPESAFE = ProviderGuess(
    "typesafe", "https://api.typesafe.ai",
    ("jev-latest",),
    "TypeSafe Jev — native System One",
)


def detect_provider(key: str) -> ProviderGuess:
    k = key.strip()
    if k.startswith("sk-or-"):
        return _OPENROUTER
    if k.startswith("ts-") or k.startswith("tsk_"):
        return _TYPESAFE
    if k.startswith("sk-ant-"):
        return ProviderGuess("unsupported:anthropic", note=(
            "Anthropic key detected — Anthropic speaks /v1/messages, not "
            "/v1/systemone. Create a free OpenRouter key (openrouter.ai/keys) "
            "and paste that instead."))
    if k.startswith("gsk_"):
        return ProviderGuess("unsupported:groq", note=(
            "Groq key detected — not System One compatible. "
            "Use an OpenRouter key (openrouter.ai/keys)."))
    if k.startswith("sk-proj-") or k.startswith("sk-"):
        return ProviderGuess("unsupported:openai", note=(
            "OpenAI key detected — not System One compatible. "
            "Use an OpenRouter key (openrouter.ai/keys) or a TypeSafe key."))
    return ProviderGuess("unknown")


def provider_by_id(pid: str) -> ProviderGuess:
    return {"openrouter": _OPENROUTER, "typesafe": _TYPESAFE}.get(pid, ProviderGuess(pid))


def pick_model(guess: ProviderGuess, *, low_power: bool = False) -> str:
    """Device-aware default: hosted models are small enough that the wire
    cost dominates; low-power devices still prefer the cheapest first."""
    models = guess.default_models
    if not models:
        return ""
    return models[0]
