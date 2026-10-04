from __future__ import annotations

from snapdec.runtime import uvx_guard


def test_is_ephemeral_true_for_uv_cache(monkeypatch, tmp_path):
    monkeypatch.delenv(uvx_guard.GUARD_ENV, raising=False)
    p = tmp_path / "uv" / "cache" / "archive-v0" / "abc"
    assert uvx_guard.is_ephemeral(str(p))
    p = tmp_path / "uv" / "cache" / "environments-v2" / "snapdec"
    assert uvx_guard.is_ephemeral(str(p))


def test_not_ephemeral_for_tool_install_or_venv(monkeypatch, tmp_path):
    monkeypatch.delenv(uvx_guard.GUARD_ENV, raising=False)
    assert not uvx_guard.is_ephemeral(str(tmp_path / "uv" / "tools" / "snapdec"))
    assert not uvx_guard.is_ephemeral(str(tmp_path / ".venv"))
    assert not uvx_guard.is_ephemeral(str(tmp_path / "plain" / "env"))


def test_guard_env_breaks_loop(monkeypatch, tmp_path):
    monkeypatch.setenv(uvx_guard.GUARD_ENV, "1")
    assert not uvx_guard.is_ephemeral(str(tmp_path / "uv" / "cache" / "archive-v0" / "x"))


def test_persist_fails_open_without_uv(monkeypatch):
    monkeypatch.setattr(uvx_guard.shutil, "which", lambda name: None)
    assert uvx_guard.persist_and_exec() is False  # warns, never raises
