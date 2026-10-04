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
