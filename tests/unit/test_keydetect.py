from __future__ import annotations

from snapdec.backends.keydetect import (
    _OPENROUTER,
    detect_provider,
    pick_model,
    provider_by_id,
)


def test_openrouter_prefix():
    g = detect_provider("sk-or-v1-abc123")
    assert g.provider == "openrouter"
    assert g.url == "https://openrouter.ai/api/v1"
    assert g.default_models == ("typesafe/jev-router",)  # only live id (2026-10-04)


def test_openrouter_chain_has_no_dead_ids():
    # kev-* ids were delisted from OpenRouter; guard against regression.
    for mid in _OPENROUTER.default_models:
        assert mid.startswith("typesafe/"), mid
        assert "jaredpalmer/" not in mid, mid


def test_typesafe_prefix():
    assert detect_provider("ts-deadbeef").provider == "typesafe"
    assert detect_provider("tsk_xyz").provider == "typesafe"


def test_unsupported_providers_get_hint_not_misroute():
    g = detect_provider("sk-ant-xyz")
    assert g.provider == "unsupported:anthropic" and "OpenRouter" in g.note
    g = detect_provider("gsk_123")
    assert g.provider == "unsupported:groq"
    g = detect_provider("sk-proj-xyz")
    assert g.provider == "unsupported:openai"


def test_unknown_key_format():
    assert detect_provider("weirdkey123").provider == "unknown"


def test_pick_model():
    g = provider_by_id("typesafe")
    assert pick_model(g) == "jev-latest"
    assert pick_model(provider_by_id("custom-x")) == ""
