"""Auto-probe local System One servers (§9.1 local = auto, no typing).

Scans localhost ports used by kev.serve / laya-serve / custom servers and
reads each server's own /v1/models so the model choice is automatic too.
The snapdec daemon port (48712) is excluded — that would find ourselves.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from .ipc import DEFAULT_PORT

COMMON_PORTS = [8901, 8009, 8321, 8080, 3000, 8000, 5000]  # managed, kev.serve, misc


@dataclass
class FoundServer:
    port: int
    models: list[str]
    server: str  # header-derived hint

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def model(self) -> str:
        return self.models[0] if self.models else ""


def _probe_one(port: int, timeout: float = 0.6) -> FoundServer | None:
    base = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(f"{base}/v1/models")
            if r.status_code == 404:  # laya-serve: /models
                r = c.get(f"{base}/models")
            if r.status_code != 200:
                return None
            server = r.headers.get("server", "")
            data = r.json()
            models: list[str] = []
            if isinstance(data, dict):
                raw = data.get("models") or data.get("data") or []
                for m in raw:
                    if isinstance(m, str):
                        models.append(m)
                    elif isinstance(m, dict) and m.get("id"):
                        models.append(str(m["id"]))
            return FoundServer(port=port, models=models, server=server)
    except (httpx.HTTPError, ValueError):
        return None


def probe_local_systemone(extra_ports: list[int] | None = None) -> list[FoundServer]:
    ports = [p for p in (extra_ports or []) + COMMON_PORTS if p != DEFAULT_PORT]
    seen: set[int] = set()
    found: list[FoundServer] = []
    for p in ports:
        if p in seen:
            continue
        seen.add(p)
        f = _probe_one(p)
        if f:
            found.append(f)
    return found
