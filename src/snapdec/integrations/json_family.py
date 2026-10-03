"""Shared integrator for the JSON `mcpServers`-family agents.

Cursor / Windsurf / Antigravity / Cline all use:
  { "mcpServers": { "<name>": {"command": ..., "args": [...]} } }
with different paths and small variations (Windsurf/Antigravity use
`serverUrl` for remote servers — we are stdio, so unaffected).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .._brand import NAME
from .base import Action, Detection, InstallManifest, Result, install_skill, mcp_entry
from .patchers import jsonc_merge


def _read_config_tolerant(path: Path) -> dict | None:
    """Verify-time parse only (read-only): tolerate comments/trailing commas.
    Writing still refuses commented files (§8.2 rule 4)."""
    import json
    import re

    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    stripped = re.sub(r"^\s*(//|#).*?$", "", text, flags=re.M)
    stripped = re.sub(r",(\s*[}\]])", r"\1", stripped)
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


class JsonFamilyIntegrator:
    id = "generic-json"
    display_name = "Generic JSON agent"
    config_path: Path | None = None       # global config
    top_key = "mcpServers"
    skills_dir: Path | None = None
    needs_restart = True
    detect_cli: str | None = None         # binary whose presence = installed

    def _entry(self, cmd: list[str]) -> dict:
        e = mcp_entry(cmd)
        e.pop("type", None)
        return e

    def detect(self) -> Detection:
        installed = False
        evidence = []
        if self.detect_cli and shutil.which(self.detect_cli):
            installed = True
            evidence.append(f"CLI `{self.detect_cli}` on PATH")
        if self.config_path and self.config_path.exists():
            installed = True
            evidence.append(str(self.config_path))
        return Detection(installed, "; ".join(evidence),
                         config_paths=[str(self.config_path)] if self.config_path else [])

    def plan(self, cmd: list[str]) -> list[Action]:
        actions = [Action("JSON_MERGE", f"{self.top_key}.{NAME} → {self.config_path}",
                          target=str(self.config_path))]
        if self.skills_dir:
            actions.append(Action("COPY_SKILL", str(self.skills_dir)))
        return actions

    def apply(self, cmd: list[str], dry_run: bool = False) -> Result:
        manifest = InstallManifest()
        actions: list[Action] = []
        snippets: list[str] = []
        if self.config_path is None:
            return Result(False, "no config path")
        if not dry_run:
            out = jsonc_merge(self.config_path,
                              {self.top_key: {NAME: self._entry(cmd)}},
                              manifest=manifest)
            actions.extend(out.actions)
            if out.snippet:
                snippets.append(out.snippet)
        if self.skills_dir and not dry_run:
            actions.append(install_skill(self.skills_dir, manifest))
        return Result(
            ok=True,
            detail="; ".join(a.detail for a in actions) or "already configured",
            actions=actions,
            needs_restart=self.needs_restart,
            manual_snippet="\n\n".join(snippets),
        )

    def verify(self) -> list[tuple[bool, str]]:
        if not self.config_path or not self.config_path.exists():
            return [(False, f"{self.display_name}: config missing")]
        data = _read_config_tolerant(self.config_path)
        if data is None:
            return [(False, f"{self.display_name}: config unreadable")]
        ok = NAME in (data.get(self.top_key) or {})
        return [(ok, f"{self.display_name}: {'registered' if ok else 'not registered'}")]

    def remove(self) -> Result:
        import json

        from .base import atomic_write, backup_file, load_json
        if not self.config_path or not self.config_path.exists():
            return Result(True, "nothing to remove")
        data, err = load_json(self.config_path)
        if data is None:
            return Result(False, f"hands off: {err}")
        servers = data.get(self.top_key)
        if not isinstance(servers, dict) or NAME not in servers:
            return Result(True, "not registered")
        bak = backup_file(self.config_path)
        del servers[NAME]
        atomic_write(self.config_path, json.dumps(data, indent=2) + "\n")
        if self.skills_dir and self.skills_dir.exists():
            import shutil as sh

            sh.rmtree(self.skills_dir, ignore_errors=True)
        return Result(True, f"removed (backup: {bak})")
