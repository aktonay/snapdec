"""Ephemeral-run guard (§5.3): uvx cache environments don't survive.

`uvx snapdec init` runs from uv's ephemeral cache. Agent registrations
written with that interpreter path break on the next cache clear. The
guard detects the cache env, persists a real tool install, and re-execs
from it. Fail-open by design — a UX guard, not a safety control.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .._brand import __version__

GUARD_ENV = "SNAPDEC_UVX_GUARD"


def is_ephemeral(prefix: str | None = None) -> bool:
    """True when running from a uvx cache env (uv/tools installs are NOT flagged)."""
    if os.environ.get(GUARD_ENV) == "1":
        return False  # re-exec child — break the loop
    parts = Path(prefix or sys.prefix).resolve().parts
    return "uv" in parts and any(
        p == "cache" or p.startswith("archive-v") or p.startswith("environments-v")
        for p in parts
    )


def persist_and_exec() -> bool:
    """Install snapdec as a persistent uv tool and re-exec this command.

    Returns False (after a warning) when persistence is impossible; the
    caller continues in the ephemeral env rather than failing the run.
    """
    uv = shutil.which("uv")
    if uv is None:
        print("[warn] running from an ephemeral uvx env — registered paths "
              "won't survive a cache clear. Install persistently first: "
              "`uv tool install snapdec` (or pipx install snapdec).")
        return False
    for args in ([uv, "tool", "install", f"snapdec=={__version__}"],
                 [uv, "tool", "install", "snapdec"]):
        r = subprocess.run(args, capture_output=True, text=True, timeout=600)
        if r.returncode == 0:
            break
    else:
        print(f"[warn] uv tool install failed: {r.stderr[-200:]}"  # type: ignore[union-attr]
              " — continuing in the ephemeral env.")
        return False
    exe = shutil.which("snapdec")
    if exe is None:
        print("[warn] installed, but `snapdec` not on PATH yet — restart the "
              "terminal and re-run.")
        return False
    env = dict(os.environ, **{GUARD_ENV: "1"})
    rc = subprocess.run([exe, *sys.argv[1:]], env=env).returncode
    sys.exit(rc)


def guard() -> None:
    if is_ephemeral():
        print("[info] ephemeral uvx environment — persisting snapdec as a uv tool…")
        persist_and_exec()
