"""Integrator contract + the config-safety toolkit (§8.1, §8.2).

Hard rules baked into the helpers (violating any of these is R8 —
"config corruption of other tools", severity: Severe):

1. CLI-first where the agent ships one.
2. Backup before first modification (<file>.bak-<UTC timestamp>).
3. Atomic write (temp file + os.replace), permissions preserved.
4. Unknown keys and key order preserved; comments preserved (TOML via
   tomlkit); JSONC-with-comments is NEVER rewritten — snippet printed.
5. Parse failure = hands off (report, never "repair").
6. Idempotent: identical entry → no-op.
7. Every touch recorded in the install manifest for exact reversal.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .. import config

# ---------------------------------------------------------------- types


@dataclass
class Action:
    kind: str  # CLI | JSON_MERGE | JSONC_PATCH | TOML_MERGE | COPY_SKILL | APPEND_BLOCK
    detail: str
    target: str = ""


@dataclass
class Detection:
    installed: bool
    evidence: str = ""
    version: str = ""
    config_paths: list[str] = field(default_factory=list)


@dataclass
class Result:
    ok: bool
    detail: str = ""
    actions: list[Action] = field(default_factory=list)
    needs_restart: bool = False
    manual_snippet: str = ""  # printed when we must not write (§8.2 rule 4)


@runtime_checkable
class Integrator(Protocol):
    id: str
    display_name: str

    def detect(self) -> Detection: ...
    def plan(self, exe: str) -> list[Action]: ...
    def apply(self, exe: str, dry_run: bool = False) -> Result: ...
    def verify(self) -> list[tuple[bool, str]]: ...
    def remove(self) -> Result: ...


# ---------------------------------------------------------------- manifest


class InstallManifest:
    """Records every file we touched so uninstall reverses exactly."""

    def __init__(self) -> None:
        self.path = config.installed_manifest_path()
        self.data: dict[str, Any] = {"files": {}, "skills": []}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

    def record_file(self, path: Path, backup: Path | None) -> None:
        files = self.data.setdefault("files", {})
        entry = files.get(str(path), {})
        entry["backup"] = str(backup) if backup else entry.get("backup")
        if backup:
            entry.setdefault("original_backup", str(backup))
        files[str(path)] = entry
        self._save()

    def record_skill(self, dest: str) -> None:
        skills = self.data.setdefault("skills", [])
        if dest not in skills:
            skills.append(dest)
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)


# ---------------------------------------------------------------- helpers


def backup_file(path: Path) -> Path | None:
    """Timestamped backup; never overwrites an older one (§8.2 rule 2)."""
    if not path.exists():
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = path.with_name(f"{path.name}.bak-{ts}")
    if not bak.exists():
        shutil.copy2(path, bak)
    return bak


def atomic_write(path: Path, content: str, *, mode: int | None = None) -> None:
    """Temp file in the same dir + os.replace; preserve permissions (rule 3)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.sysone-tmp")
    tmp.write_text(content, encoding="utf-8")
    if mode is not None:
        os.chmod(tmp, mode)
    elif path.exists():
        os.chmod(tmp, path.stat().st_mode & 0o7777)
    os.replace(tmp, path)


def load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    """Strict load. Returns (None, reason) on any parse problem (rule 5)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text), ""
    except FileNotFoundError:
        return {}, ""
    except (OSError, json.JSONDecodeError) as e:
        return None, f"parse failure ({e}) — hands off"


def merge_dict(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge that never drops unknown keys (rule 4)."""
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            merge_dict(base[k], v)
        else:
            base[k] = v
    return base


def skill_source_dir() -> Path:
    return Path(__file__).parent.parent / "skills" / "sysone"


def install_skill(dest_dir: Path, manifest: InstallManifest) -> Action:
    """Copy the packaged SKILL.md tree to an agent's skills dir."""
    src = skill_source_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f in src.rglob("*"):
        if f.is_file():
            target = dest_dir / f.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
    manifest.record_skill(str(dest_dir))
    return Action("COPY_SKILL", f"skill → {dest_dir}", target=str(dest_dir))


def mcp_entry(exe: str) -> dict[str, Any]:
    """Standard stdio server entry for `sysone`."""
    return {"type": "stdio", "command": exe, "args": ["mcp"], "env": {}}
