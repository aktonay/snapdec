"""Version check + self-update (§5.3 'changing later', ADR-0009).

Design: notice-only by default — `snapdec update` acts. The automatic
check fetches public PyPI metadata (a plain GET; nothing about the user
is sent — the no-telemetry rule §0.5 is about user data, not public
metadata reads) and is cached for 24 h in the state dir so commands don't
hit the network on every run.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time

from .. import config
from .._brand import __version__

PYPI_URL = "https://pypi.org/pypi/snapdec/json"
CHECK_TTL = 24 * 3600


def _cache_file():
    return config.state_dir() / "update_check.json"


def latest_version(*, force: bool = False) -> str | None:
    """Latest version on PyPI, or None (offline/older-than-TTL cache)."""
    now = time.time()
    if not force:
        try:
            c = json.loads(_cache_file().read_text(encoding="utf-8"))
            if now - float(c.get("ts", 0)) < CHECK_TTL:
                return c.get("latest") or None
        except (OSError, ValueError):
            pass
    try:
        import httpx

        with httpx.Client(timeout=3.0) as cli:
            r = cli.get(PYPI_URL)
        r.raise_for_status()
        latest = r.json()["info"]["version"]
    except Exception:  # noqa: BLE001 — offline is a normal state, not an error
        return None
    try:
        _cache_file().parent.mkdir(parents=True, exist_ok=True)
        _cache_file().write_text(
            json.dumps({"ts": now, "latest": latest}), encoding="utf-8")
    except OSError:
        pass
    return latest


def update_notice(*, force: bool = False) -> str | None:
    """One-line notice when a newer version exists; None when current."""
    latest = latest_version(force=force)
    if not latest or latest == __version__:
        return None
    return (f"snapdec {latest} available (you have {__version__}) — "
            f"run `snapdec update`")


def _run(cmd: list[str]) -> bool:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        sys.stderr.write((r.stderr or r.stdout)[-400:] + "\n")
    return r.returncode == 0


def self_update() -> tuple[bool, str]:
    """Upgrade the snapdec installation (uv tool → pip → pipx)."""
    if shutil.which("uv"):
        if _run(["uv", "tool", "install", "--upgrade", "snapdec"]):
            return True, "uv tool upgraded"
        # not installed as a uv tool (pip/pipx/source) — fall through
    py = sys.executable
    if _run([py, "-m", "pip", "install", "--upgrade", "snapdec"]):
        return True, "pip upgraded"
    if shutil.which("pipx") and _run(["pipx", "upgrade", "snapdec"]):
        return True, "pipx upgraded"
    return False, ("could not upgrade automatically — install the new version "
                   "manually: uv tool install --upgrade snapdec")
