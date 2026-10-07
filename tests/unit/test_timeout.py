"""ADR-0010 §6: request timeouts derive from Config, not hardcodes.

`effective_request_timeout()`: explicit override wins; local-managed /
local-server get 60 s (CPU models can take seconds/question under the
8-way CLI fan-out); hosted stays at 5 s. Threaded through
`daemon.build_backend`, `ipc._client`, `cli._canary`.
"""

from __future__ import annotations

from snapdec import config


def test_effective_timeout_explicit_override_wins():
    cfg = config.Config(backend="remote", backend_label="hosted",
                        request_timeout_s=12.5)
    assert cfg.effective_request_timeout() == 12.5


def test_effective_timeout_local_managed_gets_60():
    cfg = config.Config(backend="remote", backend_label="local-managed")
    assert cfg.effective_request_timeout() == 60.0


def test_effective_timeout_local_server_gets_60():
    cfg = config.Config(backend="remote", backend_label="local-server")
    assert cfg.effective_request_timeout() == 60.0


def test_effective_timeout_hosted_and_unset_get_5():
    assert config.Config(backend="remote", backend_label="hosted") \
        .effective_request_timeout() == 5.0
    assert config.Config(backend="tier0").effective_request_timeout() == 5.0


def test_load_drops_unknown_keys_and_reads_timeout(tmp_home):
    import json

    p = config.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"backend": "remote", "stale_field": 1,
                             "request_timeout_s": 33.0}), encoding="utf-8")
    cfg = config.Config.load()
    assert cfg.request_timeout_s == 33.0  # and no TypeError from stale_field


def test_build_backend_passes_effective_timeout(tmp_home, monkeypatch):
    from snapdec.runtime import daemon

    seen: dict[str, float] = {}

    class StubBackend:
        def __init__(self, base_url, model="", api_key=None, timeout=5.0):
            seen["timeout"] = timeout

    monkeypatch.setattr(daemon, "RemoteSystemOne", StubBackend)
    daemon.build_backend(config.Config(
        backend="remote", backend_label="local-managed",
        remote_url="http://127.0.0.1:8903", model="vllm-sr/Decision-2.0-Eos-0.8B"))
    assert seen["timeout"] == 60.0


def test_ipc_client_uses_configured_timeout(tmp_home, monkeypatch):
    from snapdec.runtime import ipc

    cfg = config.Config(request_timeout_s=33.0)
    cfg.save()
    ipc.write_state(pid=1, port=48712, token="t", transport="tcp")

    seen: dict[str, float] = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            seen["timeout"] = kwargs.get("timeout")

    monkeypatch.setattr(ipc.httpx, "Client", FakeClient)
    ipc._client()
    assert seen["timeout"] == 33.0
