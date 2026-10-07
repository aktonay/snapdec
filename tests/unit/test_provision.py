from __future__ import annotations

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
    with pytest.raises(ValueError, match="unknown backend kind"):
        provision.port_for("nope")


def test_default_model_per_kind():
    assert provision._default_model("laya") == "english"
    assert provision._default_model("kev") == "jaredpalmer/kev-0.8b"
    assert provision._default_model("decision2") == D2_EOS  # eos = this-PC rec


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
