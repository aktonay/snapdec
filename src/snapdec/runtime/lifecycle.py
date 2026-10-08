"""Daemon lifecycle: lazy start by the shim, status, stop, warm (§4.4)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any

from .. import config
from . import ipc


def _which_snapdec() -> os.PathLike[str] | None:
    import shutil

    return shutil.which("snapdec")


def _snapdec_cmd() -> list[str]:
    """Absolute command to run `snapdec` (NFR-6: never rely on PATH)."""
    exe = _which_snapdec()
    if exe:
        return [str(exe)]
    return [sys.executable, "-m", "snapdec.cli"]  # resolves to cli/__main__.py


def start_daemon(wait_seconds: float = 10.0) -> bool:
    """Spawn a detached daemon; wait until it answers /healthz."""
    from .. import config as _cfg

    try:  # managed local backend: resurrect laya if it died
        from . import provision

        provision.ensure_running(_cfg.Config.load())
    except Exception:
        pass
    if ipc.ping():
        return True
    cmd = _snapdec_cmd() + ["daemon", "start-foreground"]
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True
    logs = config.logs_dir()
    logs.mkdir(parents=True, exist_ok=True)
    out = open(logs / "daemon.out", "ab")
    try:
        subprocess.Popen(cmd, stdout=out, stderr=out, stdin=subprocess.DEVNULL, **kwargs)
    finally:
        out.close()
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if ipc.ping():
            return True
        time.sleep(0.2)
    return False


def stop_daemon() -> bool:
    """POST /shutdown; fall back to terminating the recorded PID."""
    import httpx

    url = ipc.daemon_url()
    st = ipc.read_state()
    if url and st:
        token = st.get("token", "")
        try:
            if url.startswith("http+unix://"):
                transport = httpx.HTTPTransport(uds=url.removeprefix("http+unix://"))
                base = "http://localhost"
            else:
                transport = httpx.HTTPTransport()
                base = url
            with httpx.Client(transport=transport, base_url=base,
                              headers={"authorization": f"Bearer {token}"},
                              timeout=5.0) as c:
                c.post("/shutdown")
        except httpx.HTTPError:
            pass
    # wait for graceful exit, then check PID
    for _ in range(20):
        if not _pid_alive(st.get("pid") if st else None):
            ipc.clear_state()
            return True
        time.sleep(0.2)
    if st and st.get("pid") and _pid_alive(st.get("pid")):
        # name-checked (see _pid_alive): never terminate a PID that Windows
        # has handed to an unrelated process (ADR-0011)
        try:
            import psutil

            psutil.Process(int(st["pid"])).terminate()
            ipc.clear_state()
            return True
        except (psutil.Error, ValueError):
            pass
    ipc.clear_state()
    return not _pid_alive(st.get("pid") if st else None)


def _pid_alive(pid: Any) -> bool:
    if not pid:
        return False
    try:
        import psutil

        p = psutil.Process(int(pid))
        if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
            return False
        # Windows reuses PIDs aggressively: a stale state file can point at
        # an unrelated process. The daemon runs as a python process — a pid
        # held by anything else is not ours (ADR-0011).
        name = p.name().lower()
        return name.startswith("python") or "snapdec" in name
    except (psutil.Error, ValueError):
        return False


def daemon_status() -> dict[str, Any]:
    st = ipc.read_state()
    alive = _pid_alive(st.get("pid") if st else None)
    healthy = ipc.ping()
    return {"state_file": bool(st), "pid": st.get("pid") if st else None,
            "alive": alive, "healthy": healthy,
            "transport": st.get("transport") if st else None,
            "started_at": st.get("started_at") if st else None}


def warm_daemon() -> bool:
    """Ensure running + one canary request through the full stack."""
    if not start_daemon():
        return False
    try:
        r = ipc.call_systemone({
            "state": "canary",
            "questions": {"ok": {"type": "noul", "instructions": "warmup ping"}},
        })
        return "answers" in r
    except ConnectionError:
        return False
