"""Remote /v1/systemone backend (§6).

Works unchanged with: hosted TypeSafe Jev, OpenRouter-hosted models,
kev.serve, laya-serve, team servers, Telnyx/Opper/LLM Gateway.
Fail-closed: any transport error raises; the daemon converts it into a
`review` envelope — never into an exception toward the host agent.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..decisions.envelope import (
    Answer,
    SystemOneRequest,
    SystemOneResponse,
)
from .base import Health


class RemoteSystemOne:
    id = "remote"

    def __init__(self, base_url: str, model: str = "", api_key: str | None = None,
                 timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    # ---------------------------------------------------------------- http
    def _headers(self) -> dict[str, str]:
        h = {"content-type": "application/json"}
        if self.api_key:
            h["authorization"] = f"Bearer {self.api_key}"
            h["x-api-key"] = self.api_key  # kev.serve / laya-serve convention
        return h

    def load(self) -> None:
        pass  # no local state; readiness checked via health()

    def system_one(self, req: SystemOneRequest) -> SystemOneResponse:
        payload = req.model_dump(exclude_none=True)
        if self.model:
            payload["model"] = self.model
        r = httpx.post(
            f"{self.base_url}/v1/systemone",
            json=payload, headers=self._headers(), timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        answers = {k: Answer(**v) for k, v in (data.get("answers") or {}).items()}
        return SystemOneResponse(answers=answers, usage=data.get("usage"),
                                 model=data.get("model"))

    def health(self) -> Health:
        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.get(f"{self.base_url}/v1/models", headers=self._headers())
                if r.status_code == 404:  # laya-serve exposes /models, not /v1/models
                    r = c.get(f"{self.base_url}/models", headers=self._headers())
                if r.status_code in (200, 401, 403):
                    # 401/403 = server is up, key is wrong — still "reachable"
                    status = "ready" if r.status_code == 200 else "degraded"
                    return Health(status=status, device="remote",
                                  detail=f"HTTP {r.status_code}")
                return Health(status="degraded", device="remote",
                              detail=f"HTTP {r.status_code}")
        except httpx.HTTPError as e:
            return Health(status="failed", device="remote", detail=str(e))

    def close(self) -> None:
        pass

    def describe(self) -> dict[str, Any]:
        return {"name": self.id, "url": self.base_url, "model": self.model,
                "remote": True}
