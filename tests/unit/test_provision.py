from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from snapdec.runtime import provision


def test_kev_pin_is_kev_1_0():
    assert provision.KEV_PIN_SHA == "fe64b1274ea7f80d4095866df90666abb03e9cf6"
    assert len(provision.KEV_PIN_SHA) == 40
    assert provision.KEV_TARBALL.endswith(f"{provision.KEV_PIN_SHA}.tar.gz")


def test_install_backend_kev_uses_serve_extra(monkeypatch):
    specs: list[tuple] = []

    def fake_pip(py, *s):
        specs.append(s)

    monkeypatch.setattr(provision, "_pip_install", fake_pip)
    monkeypatch.setattr(provision, "_python_ok_for_kev", lambda py: True)
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="0.1.0", stderr=""))
    provision.install_backend(py=None, kind="kev")  # type: ignore[arg-type]
    assert specs == [(f"kev[serve] @ {provision.KEV_TARBALL}",)]


def test_install_backend_kev_refuses_wrong_python(monkeypatch):
    monkeypatch.setattr(provision, "_python_ok_for_kev", lambda py: False)
    with pytest.raises(RuntimeError, match="3.12"):
        provision.install_backend(py=None, kind="kev")  # type: ignore[arg-type]


@pytest.mark.parametrize("repo", ["kev-0.8b", "kev-4b", "kev-9b", "kev-27b"])
def test_launch_cmd_kev_all_sizes(repo):
    cmd = provision._launch_cmd("kev", f"jaredpalmer/{repo}")
    assert cmd[-6:] == ["-m", "kev.serve", "--run", f"jaredpalmer/{repo}",
                        "--port", "8902"]


def test_setup_size_note_per_model():
    assert "60 GB" in provision.setup_size_note("kev", "jaredpalmer/kev-27b")
    assert "12 GB" in provision.setup_size_note("kev", "jaredpalmer/kev-4b")
    assert "22 GB" in provision.setup_size_note("kev", "jaredpalmer/kev-9b")
    assert "5 GB" in provision.setup_size_note("kev", "jaredpalmer/kev-0.8b")
    assert "5 GB" in provision.setup_size_note("kev")  # default
    assert "2 GB" in provision.setup_size_note("laya")


# ------------------------------------------------------------ decision2 (ADR-0010)

D2_EOS = "vllm-sr/Decision-2.0-Eos-0.8B"


def test_d2_repos_are_org_prefixed_pinned_commits():
    for repo, pin in provision.D2_REPOS.items():
        assert repo.startswith("vllm-sr/") and len(repo.split("/", 1)[1]) > 0
        assert len(pin) == 40
        assert all(c in "0123456789abcdef" for c in pin)


def test_install_backend_decision2_pins_specs_and_materializes(
        monkeypatch, tmp_home):
    specs: list[tuple] = []

    def fake_pip(py, *s):
        specs.append(s)

    monkeypatch.setattr(provision, "_pip_install", fake_pip)
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="5.18.0", stderr=""))
    note = provision.install_backend(py=None, kind="decision2")  # type: ignore[arg-type]
    assert specs == [provision.D2_INSTALL_SPECS]
    assert "5.18.0" in note and "d2serve.py" in note
    script = provision.runtime_dir() / "d2serve.py"
    assert script.exists()
    assert script.read_text(encoding="utf-8") == \
        Path(provision.__file__).with_name("d2serve.py").read_text(encoding="utf-8")


def test_materialize_d2serve_idempotent(tmp_home):
    a = provision._materialize_d2serve()
    before = a.read_text(encoding="utf-8")
    mtime = a.stat().st_mtime_ns
    b = provision._materialize_d2serve()
    assert a == b
    assert b.read_text(encoding="utf-8") == before
    assert b.stat().st_mtime_ns == mtime  # unchanged → no rewrite


def test_launch_cmd_decision2_shape(tmp_home):
    cmd = provision._launch_cmd("decision2", D2_EOS)
    assert cmd[1].endswith("d2serve.py")
    assert cmd[2:] == ["--repo", D2_EOS,
                       "--revision", provision.D2_REPOS[D2_EOS],
                       "--port", "8903"]


def test_port_for_all_kinds():
    assert provision.port_for("laya") == 8901
    assert provision.port_for("kev") == 8902
    assert provision.port_for("decision2") == 8903
    assert provision.port_for("imajev") == 8904
    with pytest.raises(ValueError, match="unknown backend kind"):
        provision.port_for("nope")


def test_default_model_per_kind():
    assert provision._default_model("laya") == "english"
    assert provision._default_model("kev") == "jaredpalmer/kev-0.8b"
    assert provision._default_model("decision2") == D2_EOS  # eos = this-PC rec
    assert provision._default_model("imajev") == "mohit67890/imajev-2b"


def test_setup_size_note_decision2():
    assert "2 GB" in provision.setup_size_note("decision2",
                                               "vllm-sr/Decision-2.0-Kai-0.6B")
    assert "3 GB" in provision.setup_size_note("decision2", D2_EOS)
    assert "11 GB" in provision.setup_size_note("decision2",
                                               "vllm-sr/Decision-2.0-Nox-4B")
    assert "3 GB" in provision.setup_size_note("decision2")  # default = eos


def test_provision_rejects_unknown_d2_model(tmp_home):
    ok, detail = provision.provision("decision2", "vllm-sr/Decision-2.0-Vega-27B",
                                     consent=True)
    assert ok is False
    assert "unknown Decision 2.0 model" in detail


# ------------------------------------------------------------ imajev (ADR-0011)


def test_imajev_pins_are_full_shas():
    assert len(provision.IMAJEV_PIN_SHA) == 40
    assert provision.IMAJEV_TARBALL.endswith(f"{provision.IMAJEV_PIN_SHA}.tar.gz")
    for repo, pin in provision.IMAJEV_REPOS.items():
        assert repo.startswith("mohit67890/imajev-")
        assert len(pin) == 40
        assert all(c in "0123456789abcdef" for c in pin)
    for size, (base, rev, bundle) in provision.IMAJEV_BASE_PINS.items():
        assert base == f"Qwen/Qwen3.5-{size.upper()}"
        assert len(rev) == 40
        assert all(c in "0123456789abcdef" for c in rev)
        assert bundle.startswith("artifacts/model")


def test_imajev_install_specs_fully_pinned():
    for spec in provision.IMAJEV_INSTALL_SPECS:
        assert "==" in spec
        assert not any(op in spec for op in (">=", "<=", "~=", ">", "<", "!="))


class _TarballResp:
    content = b""

    def raise_for_status(self):
        pass


class _TarballClient:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url):
        return _TarballResp()


class _FakeTar:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def getmembers(self):
        return []

    def extractall(self, *a, **k):
        pass


def test_install_imajev_idempotent_marker_skip(tmp_home, monkeypatch):
    # marker gates the tarball extract only — deps always pip-install
    # (spec list can grow across releases; pip is an idempotent no-op)
    root = provision._imajev_dir()
    root.mkdir(parents=True)
    (root / ".snapdec-ok").write_text(provision.IMAJEV_PIN_SHA, encoding="utf-8")
    specs: list[tuple] = []

    def boom(*a, **k):
        raise AssertionError("marker present — no network allowed")

    monkeypatch.setattr(provision.httpx, "Client", boom)
    monkeypatch.setattr(provision, "_pip_install", lambda py, *s: specs.append(s))
    assert provision._install_imajev(Path("py")) == \
        f"imajev-{provision.IMAJEV_PIN_SHA[:8]}"
    assert specs == [provision.IMAJEV_INSTALL_SPECS]


def test_install_imajev_appends_mlx_vlm_only_on_darwin(tmp_home, monkeypatch):
    monkeypatch.setattr(provision.httpx, "Client", _TarballClient)
    monkeypatch.setattr(provision.tarfile, "open", lambda *a, **k: _FakeTar())
    specs: list[tuple] = []
    monkeypatch.setattr(provision, "_pip_install",
                        lambda py, *s: specs.append(s))
    monkeypatch.setattr(provision.sys, "platform", "darwin")
    provision._install_imajev(Path("py"))
    assert specs == [provision.IMAJEV_INSTALL_SPECS + ("mlx-vlm==0.7.1",)]
    assert (provision._imajev_dir() / ".snapdec-ok").exists()


def test_install_imajev_specs_plain_off_apple(tmp_home, monkeypatch):
    monkeypatch.setattr(provision.httpx, "Client", _TarballClient)
    monkeypatch.setattr(provision.tarfile, "open", lambda *a, **k: _FakeTar())
    specs: list[tuple] = []
    monkeypatch.setattr(provision, "_pip_install",
                        lambda py, *s: specs.append(s))
    monkeypatch.setattr(provision.sys, "platform", "win32")
    provision._install_imajev(Path("py"))
    assert specs == [provision.IMAJEV_INSTALL_SPECS]  # no mlx-vlm off Apple


def test_ensure_imajev_model_skips_when_present(tmp_home, monkeypatch):
    model = "mohit67890/imajev-2b"
    bundle = provision._imajev_dir() / provision.IMAJEV_BASE_PINS["2b"][2]
    bundle.parent.mkdir(parents=True, exist_ok=True)
    # real-shaped bundle: existing absolute snapshot path (their script output)
    snap = tmp_home / "runtime" / "imajev-hf" / "snap"
    snap.mkdir(parents=True)
    bundle.write_text(json.dumps({"path": str(snap), "repository_bytes": 1}),
                      encoding="utf-8")
    provision._imajev_adapter_dir(model).mkdir(parents=True)

    def boom(*a, **k):
        raise AssertionError("bundle+adapter present — no subprocess allowed")

    monkeypatch.setattr(provision.subprocess, "run", boom)
    provision._ensure_imajev_model(Path("py"), model)


def test_bundle_ready_rejects_tarball_placeholder(tmp_home):
    # their tarball SHIPS artifacts/model.json as a placeholder (relative
    # path + "note" key, no snapshot) — .exists() alone would skip the base
    # download and crash the server at load (ADR-0011 §3)
    root = provision._imajev_dir()
    bundle = root / "artifacts" / "model.json"
    bundle.parent.mkdir(parents=True)
    placeholder = {"path": ".cache/huggingface/hub/models--Qwen--Qwen3.5-2B",
                   "note": "run scripts/download_model.py"}
    bundle.write_text(json.dumps(placeholder), encoding="utf-8")
    assert provision._bundle_ready(bundle) is False
    # real script output: absolute path that exists → ready
    snap = tmp_home / "runtime" / "imajev-hf" / "snapshot"
    snap.mkdir(parents=True)
    bundle.write_text(json.dumps({"path": str(snap)}), encoding="utf-8")
    assert provision._bundle_ready(bundle) is True
    # absolute path that does NOT exist → not ready (server would crash)
    bundle.write_text(json.dumps({"path": str(snap / "missing")}),
                      encoding="utf-8")
    assert provision._bundle_ready(bundle) is False
    # missing/empty/invalid json → not ready
    assert provision._bundle_ready(root / "artifacts" / "nope.json") is False
    bundle.write_text("{}", encoding="utf-8")
    assert provision._bundle_ready(bundle) is False  # Path("") == "." trap
    bundle.write_text("{not json", encoding="utf-8")
    assert provision._bundle_ready(bundle) is False


def _launch_flags(cmd: list[str]) -> dict[str, str]:
    return {cmd[i]: cmd[i + 1] for i in range(2, len(cmd) - 1, 2)}


def test_launch_cmd_imajev_torch_shape(tmp_home, monkeypatch):
    monkeypatch.setattr(provision.sys, "platform", "win32")
    model = "mohit67890/imajev-2b"
    adapter = provision._imajev_adapter_dir(model)
    cmd = provision._launch_cmd("imajev", model)
    assert cmd[1] == str(provision._imajev_dir() / "scripts" / "playground"
                         / "server.py")
    assert _launch_flags(cmd) == {
        "--backend": "torch",  # fp32 CPU path (12/24/48 GB floors, ADR-0011)
        "--adapter": str(adapter),
        "--model-bundle": str(provision._imajev_dir() / "artifacts" / "model.json"),
        "--calibration": str(adapter / "calibration.json"),
        "--rotations": "1",  # official benchmark flag
        "--model-name": model,
        "--host": "127.0.0.1",
        "--port": "8904",
    }


def test_launch_cmd_imajev_mlx_on_darwin(tmp_home, monkeypatch):
    monkeypatch.setattr(provision.sys, "platform", "darwin")
    model = "mohit67890/imajev-9b"
    adapter = provision._imajev_adapter_dir(model)
    cmd = provision._launch_cmd("imajev", model)
    flags = _launch_flags(cmd)
    assert flags["--backend"] == "mlx"  # real MLX fast path on Apple Silicon
    assert flags["--adapter"] == str(adapter / "mlx")
    assert flags["--model-bundle"] == str(provision._imajev_dir() / "artifacts"
                                          / "model-qwen9b.json")
    assert flags["--calibration"] == str(adapter / "calibration.json")
    assert flags["--port"] == "8904"


def test_env_imajev_offline_no_pythonpath(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    env = provision._env("imajev", "mohit67890/imajev-2b")
    assert env["HF_HUB_OFFLINE"] == "1"
    assert "PYTHONPATH" not in env  # their server self-manages sys.path


class _StubResp:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


def _stub_http(responses: dict[str, _StubResp]):
    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url: str):
            for suffix, resp in responses.items():
                if url.endswith(suffix):
                    return resp
            return _StubResp(404)

    return _Client


def test_healthy_imajev_requires_loaded_true(monkeypatch):
    # their server: no /health; uvicorn binds only after build_backend, and
    # /v1/models answers 200 with loaded:false while the model loads
    monkeypatch.setattr(provision.httpx, "Client", _stub_http({
        "/health": _StubResp(404),
        "/healthz": _StubResp(404),
        "/v1/models": _StubResp(200, {"loaded": False}),
    }))
    assert provision._healthy("imajev") is False
    monkeypatch.setattr(provision.httpx, "Client", _stub_http({
        "/health": _StubResp(404),
        "/healthz": _StubResp(404),
        "/v1/models": _StubResp(200, {"model": "mohit67890/imajev-2b",
                                      "loaded": True}),
    }))
    assert provision._healthy("imajev") is True


def test_advertised_model_imajev_flat_body(monkeypatch):
    monkeypatch.setattr(provision.httpx, "Client", _stub_http({
        "/v1/models": _StubResp(200, {"model": "mohit67890/imajev-2b",
                                      "adapter": "imajev-2b",
                                      "backend": "torch", "loaded": True}),
    }))
    assert provision.advertised_model("imajev") == "mohit67890/imajev-2b"


def test_setup_size_note_imajev():
    assert "5 GB" in provision.setup_size_note("imajev", "mohit67890/imajev-2b")
    assert "10 GB" in provision.setup_size_note("imajev", "mohit67890/imajev-4b")
    assert "19 GB" in provision.setup_size_note("imajev", "mohit67890/imajev-9b")
    assert "5 GB" in provision.setup_size_note("imajev")  # default = 2b


def test_provision_rejects_unknown_imajev_model(tmp_home):
    ok, detail = provision.provision("imajev", "mohit67890/imajev-42b",
                                     consent=True)
    assert ok is False
    assert "unknown imajev model" in detail


# ------------------------------------------------- ensure_running (resurrect, ADR-0011)

def _resurrect_env(monkeypatch, tmp_path, *, kind: str, model: str):
    """Stub everything ensure_running touches; record wait/launch calls."""
    from snapdec import config as cfg_mod

    py = tmp_path / "venv-py"
    py.write_text("", encoding="utf-8")
    seen: dict[str, list] = {"wait": [], "launch": []}
    monkeypatch.setattr(provision, "_healthy", lambda k: False)
    monkeypatch.setattr(provision, "venv_python", lambda: py)

    def fake_wait(k, timeout=600.0, on_wait=None):
        seen["wait"].append((k, timeout))
        return False

    monkeypatch.setattr(provision, "wait_healthy", fake_wait)
    monkeypatch.setattr(provision, "launch",
                        lambda k, m: seen["launch"].append((k, m)) or 1)
    cfg = cfg_mod.Config(backend="remote", backend_label="local-managed",
                         managed=kind, model=model)
    return cfg, seen


def test_ensure_running_waits_ten_minutes_for_imajev(monkeypatch, tmp_path):
    # imajev FP32 cold load (~11 GB resident) exceeds the old 120 s window
    # (found at first real resurrect, ADR-0011)
    cfg, seen = _resurrect_env(monkeypatch, tmp_path,
                               kind="imajev", model="mohit67890/imajev-2b")
    assert provision.ensure_running(cfg) is False
    assert seen["wait"] == [("imajev", 600.0)]
    assert seen["launch"] == [("imajev", "mohit67890/imajev-2b")]


def test_ensure_running_keeps_fast_window_for_laya(monkeypatch, tmp_path):
    cfg, seen = _resurrect_env(monkeypatch, tmp_path,
                               kind="laya", model="english")
    assert provision.ensure_running(cfg) is False
    assert seen["wait"] == [("laya", 120.0)]


def test_ensure_running_failure_note_on_stderr(monkeypatch, tmp_path, capsys):
    # lifecycle.start_daemon discards the bool result — the stderr note is
    # the only visible failure surface, so it must always fire
    cfg, _ = _resurrect_env(monkeypatch, tmp_path,
                            kind="imajev", model="mohit67890/imajev-2b")
    provision.ensure_running(cfg)
    errput = capsys.readouterr().err
    assert "imajev did not become healthy" in errput
    assert "imajev.log" in errput


def test_ensure_running_short_circuits_when_healthy(monkeypatch, tmp_path):
    from snapdec import config as cfg_mod

    py = tmp_path / "venv-py"
    py.write_text("", encoding="utf-8")
    monkeypatch.setattr(provision, "_healthy", lambda k: True)
    monkeypatch.setattr(provision, "venv_python", lambda: py)
    launched: list = []
    monkeypatch.setattr(provision, "launch",
                        lambda k, m: launched.append((k, m)) or 1)
    cfg = cfg_mod.Config(backend="remote", backend_label="local-managed",
                         managed="imajev", model="mohit67890/imajev-2b")
    assert provision.ensure_running(cfg) is True
    assert launched == []


def test_ensure_running_non_managed_is_noop(monkeypatch):
    from snapdec import config as cfg_mod

    monkeypatch.setattr(provision, "_healthy",
                        lambda k: pytest.fail("must not probe non-managed"))
    cfg = cfg_mod.Config(backend="remote", backend_label="hosted",
                         model="jev-latest")
    assert provision.ensure_running(cfg) is True
