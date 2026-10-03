"""Paths and persisted configuration.

Layout (SYSONE_HOME overrides everything, for tests and portable installs):

  <data>/config.json          user choices (backend, model, agents)
  <data>/state/daemon.json    PID, port/socket, token, version, started_at
  <data>/state/daemon.sock    UDS endpoint (macOS/Linux)
  <data>/state/daemon.lock    single-instance lock
  <data>/state/keys           API keys, 0600 file fallback (ADR-006)
  <data>/state/installed.json install manifest (what we touched, for uninstall)
  <data>/logs/daemon.log      rotated logs

Keys are never written into any agent's config file (ADR-006).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

from ._brand import NAME, __version__


def home() -> Path:
    env = os.environ.get("SYSONE_HOME")
    if env:
        return Path(env)
    return Path(user_data_dir(NAME))


def data_dir() -> Path:
    return home()


def state_dir() -> Path:
    return home() / "state"


def logs_dir() -> Path:
    return home() / "logs"


def config_path() -> Path:
    return home() / "config.json"


def keys_path() -> Path:
    return state_dir() / "keys"


def installed_manifest_path() -> Path:
    return state_dir() / "installed.json"


@dataclass
class Config:
    backend: str = "tier0"  # tier0 | mock | remote
    backend_label: str = ""
    remote_url: str = ""
    model: str = ""
    api_key_env: str = ""  # name of env var holding the key; no secret stored
    api_key_stored: bool = False  # True → a key exists in state/keys (0600)
    profile: str = ""
    agents: list[str] = field(default_factory=list)
    auto_approve: bool = False
    nudge: bool = False
    created_with: str = __version__

    # ---------------------------------------------------------------- io
    def save(self) -> None:
        p = config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, p)

    @classmethod
    def load(cls) -> Config:
        p = config_path()
        if not p.exists():
            return cls()
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
        valid = {f for f in cls.__dataclass_fields__}  # ignore unknown keys
        return cls(**{k: v for k, v in data.items() if k in valid})


# ---------------------------------------------------------------- keys
def store_api_key(key: str) -> None:
    """0600-file fallback when the user has no env var to reference (ADR-006)."""
    p = keys_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(key.strip() + "\n", encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:
        pass  # Windows ACLs govern; acceptable


def get_api_key(cfg: Config) -> str | None:
    if cfg.api_key_env:
        return os.environ.get(cfg.api_key_env) or None
    if cfg.api_key_stored and keys_path().exists():
        return keys_path().read_text(encoding="utf-8").strip() or None
    return None


def mask_key(key: str | None) -> str:
    if not key:
        return "(none)"
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:6]}…{key[-4:]}"
