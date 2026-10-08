from __future__ import annotations

import json

from typer.testing import CliRunner

from snapdec._brand import __version__
from snapdec.cli.main import app
from snapdec.hardware.detect import GPU, HardwareReport

runner = CliRunner()


def _rep(**kw) -> HardwareReport:
    base = dict(os="Windows 11", arch="AMD64", cpu_model="x", cores=8,
                ram_gb=16, gpus=[])
    base.update(kw)
    return HardwareReport(**base)


def test_version():
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0
    assert f"snapdec {__version__}" in r.output


def test_models_gated(monkeypatch):
    import snapdec.cli.main as cli_mod

    monkeypatch.setattr(cli_mod, "hw_detect",
                        lambda: _rep(gpus=[GPU("Intel(R) UHD Graphics", "intel")]))
    r = runner.invoke(app, ["models"])
    assert r.exit_code == 0
    assert "Kev 0.8B" in r.output
    assert "Kev 4B" not in r.output       # 16 GB VRAM — outside spec
    assert "Kev 9B" not in r.output
    r_all = runner.invoke(app, ["models", "--all"])
    assert "Kev 4B" in r_all.output       # visible but dimmed via --all


def test_models_decision2_on_igpu_eos_starred_nox_hidden(monkeypatch):
    import snapdec.cli.main as cli_mod

    monkeypatch.setattr(cli_mod, "hw_detect",
                        lambda: _rep(gpus=[GPU("Intel(R) UHD Graphics", "intel")]))
    r = runner.invoke(app, ["models"])
    assert r.exit_code == 0
    assert "Decision 2.0 Eos 0.8B" in r.output
    assert "Decision 2.0 Sol 2B" in r.output
    assert "Decision 2.0 Nox 4B" not in r.output  # 20 GB RAM floor
    assert "(*)" in r.output                     # eos starred on windows-gpu


def test_wizard_mapping_covers_d2(monkeypatch):
    from snapdec.cli.main import WIZARD_MAPPING

    d2 = {k: v for k, v in WIZARD_MAPPING.items() if k.startswith("d2-")}
    assert d2 == {
        "d2-kai": ("decision2", "vllm-sr/Decision-2.0-Kai-0.6B"),
        "d2-eos": ("decision2", "vllm-sr/Decision-2.0-Eos-0.8B"),
        "d2-sol": ("decision2", "vllm-sr/Decision-2.0-Sol-2B"),
        "d2-nox": ("decision2", "vllm-sr/Decision-2.0-Nox-4B"),
    }
    # every mapping target must be a pinned d2 repo (case-sensitive ids)
    from snapdec.runtime.provision import D2_REPOS

    for _k, (_kind, model) in d2.items():
        assert model in D2_REPOS


def test_bench_json_mock():
    r = runner.invoke(app, ["bench", "--backend", "mock", "--json"])
    assert r.exit_code == 0
    d = json.loads(r.output)
    assert d["suite"] == "mini-v1"
    assert d["snapdec_version"] == __version__
    assert d["items"] == 12
    assert 0.0 <= d["check_brier"] <= 1.0


def test_bench_deterministic_mock():
    from snapdec.backends.mock import MockBackend
    from snapdec.bench import run_bench

    a = run_bench(MockBackend())
    b = run_bench(MockBackend())
    for k in ("classify_accuracy", "check_accuracy", "check_brier", "score_exact",
              "decision_mix", "items"):
        assert a[k] == b[k], k


def test_models_imajev_on_igpu_2b_shown_bigger_hidden(monkeypatch):
    import snapdec.cli.main as cli_mod

    monkeypatch.setattr(cli_mod, "hw_detect",
                        lambda: _rep(gpus=[GPU("Intel(R) UHD Graphics", "intel")]))
    r = runner.invoke(app, ["models"])
    assert r.exit_code == 0
    assert "imajev 2B (Qwen3.5)" in r.output
    assert "imajev 4B (Qwen3.5)" not in r.output  # 24 GB RAM floor
    assert "imajev 9B (Qwen3.5)" not in r.output
    assert "(*)" in r.output                      # d2-eos keeps the cpu/windows star
    r_all = runner.invoke(app, ["models", "--all"])
    assert "imajev 4B (Qwen3.5)" in r_all.output  # visible but dimmed via --all


def test_wizard_mapping_covers_imajev():
    from snapdec.cli.main import WIZARD_MAPPING

    im = {k: v for k, v in WIZARD_MAPPING.items() if k.startswith("imajev-")}
    assert im == {
        "imajev-2b": ("imajev", "mohit67890/imajev-2b"),
        "imajev-4b": ("imajev", "mohit67890/imajev-4b"),
        "imajev-9b": ("imajev", "mohit67890/imajev-9b"),
    }
    # every mapping target must be a pinned imajev adapter repo
    from snapdec.runtime.provision import IMAJEV_REPOS

    for _k, (_kind, model) in im.items():
        assert model in IMAJEV_REPOS
