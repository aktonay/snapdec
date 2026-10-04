from __future__ import annotations

import subprocess

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
