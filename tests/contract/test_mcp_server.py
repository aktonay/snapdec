from __future__ import annotations

import json

from snapdec.mcp.server import build_server

# pytest-asyncio auto mode (pyproject asyncio_mode=auto)


async def test_six_tools_with_short_descriptions():
    from mcp import Client

    async with Client(build_server()) as client:
        result = await client.list_tools()
        names = {t.name for t in result.tools}
        assert names == {"project_facts", "classify", "check", "score", "rank", "ask"}
        for t in result.tools:
            assert len(t.description or "") <= 300  # context budget (§0.8)


async def test_project_facts_over_mcp(tmp_path):
    from mcp import Client

    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "uv.lock").write_text("version=1\n")
    async with Client(build_server()) as client:
        res = await client.call_tool("project_facts", {"path": str(tmp_path)})
        payload = _payload(res)
        assert payload["facts"]["python_package_manager"] == "uv"
        assert payload["confidence"] == "deterministic"


async def test_tier1_fail_closed_without_daemon(tmp_path, monkeypatch):
    """No daemon → a review envelope, never an exception (NFR-4)."""
    from mcp import Client

    import snapdec.mcp.server as srv

    monkeypatch.setenv("SNAPDEC_HOME", str(tmp_path / "nowhere"))
    monkeypatch.setattr(srv, "warm_daemon", lambda: False)
    monkeypatch.setattr(srv.ipc, "ping", lambda: False)
    async with Client(build_server()) as client:
        res = await client.call_tool("classify", {
            "items": [{"id": "a", "text": "boom"}],
            "classes": {"x": "ex", "y": "why"},
        })
        payload = _payload(res)
        assert payload.get("decision") == "review"
        assert payload["summary"]["items"] == 0


async def test_tier1_with_mock_daemon(tmp_home):
    from mcp import Client

    from snapdec import config
    from snapdec.runtime.lifecycle import start_daemon, stop_daemon

    config.Config(backend="mock").save()
    ok = start_daemon(wait_seconds=20)  # cold macOS runners can be slow to spawn
    if not ok:  # surface daemon output + a direct probe — the assert alone says nothing
        from snapdec.runtime import ipc
        from snapdec.runtime.lifecycle import daemon_status

        print("status:", daemon_status())
        print("state:", ipc.read_state())
        for f in sorted(config.logs_dir().glob("*")):
            print(f"--- {f.name} ---")
            print(f.read_text(errors="replace")[:2000])
        st = ipc.read_state() or {}
        if st.get("port"):
            import httpx

            try:
                with httpx.Client(base_url=f"http://127.0.0.1:{st['port']}",
                                  timeout=5.0) as c:
                    r = c.get("/healthz")
                    print(f"direct probe: {r.status_code} {r.text[:200]}")
            except Exception as e:  # noqa: BLE001 — diagnostics only
                print(f"direct probe failed: {type(e).__name__}: {e}")
    assert ok
    try:
        async with Client(build_server()) as client:
            res = await client.call_tool("classify", {
                "items": [{"id": "t1", "text": "net error"},
                          {"id": "t2", "text": "assert error"}],
                "classes": {"infra": "net", "bug": "code"},
            })
            payload = _payload(res)
            assert len(payload["results"]) == 2
            for r in payload["results"]:
                assert r["decision"] in ("auto", "review")
                assert abs(sum(r["probabilities"].values()) - 1.0) < 1e-6
            assert payload["summary"]["items"] == 2
            # status footer: model · latency · auto mix · offload estimate
            st = payload["status"]
            assert "snapdec" in st and "ms" in st and "offloaded" in st
    finally:
        stop_daemon()


def _payload(res) -> dict:
    """v2 call_tool result → python dict (handles structured + text content)."""
    if getattr(res, "structured", None):
        return res.structured
    for c in getattr(res, "content", []):
        if getattr(c, "text", None):
            return json.loads(c.text)
    raise AssertionError(f"no payload in {res!r}")
