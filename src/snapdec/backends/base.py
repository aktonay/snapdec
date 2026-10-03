"""Backend interface (§6).

Backends are interchangeable behind one interface; anything that already
speaks /v1/systemone (hosted Jev, kev.serve, laya-serve, OpenRouter) is
just a manifest/URL away — no adapter code needed (remote_systemone).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..decisions.envelope import SystemOneRequest, SystemOneResponse


@dataclass
class Health:
    status: str  # ready | warming | degraded | failed
    device: str = ""
    detail: str = ""


@runtime_checkable
class Backend(Protocol):
    id: str

    def load(self) -> None: ...
    def system_one(self, req: SystemOneRequest) -> SystemOneResponse: ...
    def health(self) -> Health: ...
    def close(self) -> None: ...
    def describe(self) -> dict[str, Any]: ...
