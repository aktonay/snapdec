"""IPC between the MCP shim and the daemon (ADR-004).

UDS on macOS/Linux ($XDG_RUNTIME_DIR or state dir, 0600);
loopback TCP on a fixed high port + 256-bit bearer token (0600 file) on
Windows. Never binds non-loopback.

State file: <state>/daemon.json {pid, transport, port|socket, token,
version, backend, started_at}.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from .. import config
from .._brand import __version__

DEFAULT_PORT = 48712  # loopback only


def _state_file() -> Path:
    return config.state_dir() / "daemon.json"


def _uds_path() -> Path:
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    base = Path(xdg) if xdg else config.state_dir()
    return base / "snapdec.sock"


def use_uds() -> bool:
    return sys.platform != "win32"


def write_state(*, pid: int, port: int | None, token: str,
                transport: str | None = None) -> dict[str, Any]:
    """Record daemon reachability. `transport` overrides the platform default —
    the daemon may fall back to TCP when the UDS path is unusable (too long)."""
    tr = transport or ("uds" if use_uds() else "tcp")
    st = {
        "pid": pid,
        "transport": tr,
        "socket": str(_uds_path()) if tr == "uds" else None,
        "port": port if tr == "tcp" else None,
        "token": token,
        "version": __version__,
    }
    st["started_at"] = time.time()
    p = _state_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st), encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return st


def read_state() -> dict[str, Any] | None:
    p = _state_file()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def clear_state() -> None:
    _state_file().unlink(missing_ok=True)
    if use_uds():
        _uds_path().unlink(missing_ok=True)


def new_token() -> str:
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------- client


def daemon_url() -> str | None:
    st = read_state()
    if not st:
        return None
    if st.get("transport") == "uds":
        return f"http+unix://{st['socket']}"
    if st.get("port"):
        return f"http://127.0.0.1:{st['port']}"
    return None


def _client() -> httpx.Client | None:
    url = daemon_url()
    st = read_state() or {}
    token = st.get("token", "")
    if not url:
        return None
    if url.startswith("http+unix://"):
        uds = url.removeprefix("http+unix://")
        transport = httpx.HTTPTransport(uds=uds)
        base = "http://localhost"
    else:
        transport = httpx.HTTPTransport()
        base = url
    return httpx.Client(transport=transport, base_url=base,
                        headers={"authorization": f"Bearer {token}"},
                        timeout=config.Config.load().effective_request_timeout())


def ping() -> bool:
    c = _client()
    if c is None:
        return False
    try:
        with c:
            return c.get("/healthz").status_code == 200
    except httpx.HTTPError:
        return False


def call_systemone(payload: dict[str, Any]) -> dict[str, Any]:
    """POST /v1/systemone; raises on transport error (shim fails closed)."""
    c = _client()
    if c is None:
        raise ConnectionError("snapdec daemon is not running (no state file)")
    try:
        with c:
            r = c.post("/v1/systemone", json=payload)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise ConnectionError(f"daemon call failed: {e}") from e


def check_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False
