from __future__ import annotations

import json

from snapdec._brand import __version__
from snapdec.runtime import update
from snapdec.runtime.update import latest_version, update_notice


def _write_cache(latest: str, age: float = 0.0) -> None:
    import time

    update._cache_file().parent.mkdir(parents=True, exist_ok=True)
    update._cache_file().write_text(json.dumps(
        {"ts": time.time() - age, "latest": latest}), encoding="utf-8")


def test_notice_none_when_current(tmp_home):
    _write_cache(__version__)
    assert latest_version() == __version__
    assert update_notice() is None


def test_notice_when_newer(tmp_home):
    _write_cache("999.0.0")
    n = update_notice()
    assert n and "999.0.0" in n and "snapdec update" in n


def test_cache_ttl_expires(tmp_home, monkeypatch):
    _write_cache("1.0.0", age=update.CHECK_TTL + 10)
    called = []

    def fake_get(self, url):
        called.append(url)

        class R:
            def raise_for_status(self): ...

            def json(self):
                return {"info": {"version": "2.0.0"}}

        return R()

    import httpx

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    assert latest_version() == "2.0.0"
    assert called  # network was hit after TTL


def test_offline_returns_none(tmp_home, monkeypatch):
    _write_cache("1.0.0", age=update.CHECK_TTL + 10)
    import httpx

    def boom(self, url):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.Client, "get", boom)
    assert latest_version() is None


def test_self_update_uses_uv_first(monkeypatch):
    ran: list[list[str]] = []

    monkeypatch.setattr(update.shutil, "which", lambda n: "/usr/bin/uv" if n == "uv" else None)
    monkeypatch.setattr(update, "_run", lambda cmd: ran.append(cmd) or True)
    ok, detail = update.self_update()
    assert ok and detail == "uv tool upgraded"
    assert ran[0][:3] == ["uv", "tool", "install"] and "--upgrade" in ran[0]
