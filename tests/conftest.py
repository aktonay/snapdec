from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated SNAPDEC_HOME + HOME — never touch a real user config (§0.4)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SNAPDEC_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows Path.home()
    yield home
    from snapdec.runtime import lifecycle

    try:
        lifecycle.stop_daemon()
    except Exception:
        pass
    os.environ.pop("SYSONE_TEST_QUIET", None)
