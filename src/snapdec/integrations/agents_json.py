"""Cursor / Windsurf / Antigravity — JSON `mcpServers` family (§2.2).

All load MCP at startup → needs_restart=True. Global paths only;
project-scope (`--project`) is Phase 3.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .._brand import NAME
from .json_family import JsonFamilyIntegrator


class CursorIntegrator(JsonFamilyIntegrator):
    id = "cursor"
    display_name = "Cursor"
    top_key = "mcpServers"
    detect_cli = "cursor-agent"

    def __init__(self) -> None:
        self.config_path = Path.home() / ".cursor" / "mcp.json"
        self.skills_dir = Path.home() / ".cursor" / "skills" / NAME


class WindsurfIntegrator(JsonFamilyIntegrator):
    id = "windsurf"
    display_name = "Windsurf"
    top_key = "mcpServers"

    def __init__(self) -> None:
        self.config_path = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
        self.skills_dir = None  # project-level .windsurf/skills only (Phase 3)


class AntigravityIntegrator(JsonFamilyIntegrator):
    id = "antigravity"
    display_name = "Antigravity"
    top_key = "mcpServers"

    def __init__(self) -> None:
        # shared documented path; CLI-specific path is a Phase-0 spike (S6)
        self.config_path = Path.home() / ".gemini" / "config" / "mcp_config.json"
        self.skills_dir = Path.home() / ".gemini" / "antigravity" / "skills" / NAME


class OpenCodeIntegrator(JsonFamilyIntegrator):
    """OpenCode: `mcp` key, command as ARRAY, JSONC possible (§2.2)."""

    id = "opencode"
    display_name = "OpenCode"
    top_key = "mcp"

    def __init__(self) -> None:
        base = Path.home() / ".config" / "opencode"
        cfg = base / "opencode.jsonc"
        if not cfg.exists():
            cfg = base / "opencode.json"
        self.config_path = cfg
        self.skills_dir = base / "skills" / NAME

    def _entry(self, cmd: list[str]) -> dict:
        return {"type": "local", "command": cmd + ["mcp"], "enabled": True}


class VsCodeIntegrator(JsonFamilyIntegrator):
    """VS Code (Copilot agent): key `servers`, entries carry `type`."""

    id = "vscode"
    display_name = "VS Code (Copilot)"
    top_key = "servers"

    def __init__(self) -> None:
        if sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support" / "Code" / "User"
        elif sys.platform == "win32":
            base = Path.home() / "AppData" / "Roaming" / "Code" / "User"
        else:
            base = Path.home() / ".config" / "Code" / "User"
        self.config_path = base / "mcp.json"
        self.skills_dir = base / ".github" / "skills" / NAME  # ⚠️ unverified (S5)

    def detect(self) -> object:
        d = super().detect()
        # VS Code itself: check the app dir exists, not just mcp.json
        if not d.installed and self.config_path is not None:
            d.installed = self.config_path.parent.exists()
        return d


class ClineIntegrator(JsonFamilyIntegrator):
    """Cline: per-host-editor globalStorage dirs (Code, Insiders, VSCodium…)."""

    id = "cline"
    display_name = "Cline"

    def __init__(self) -> None:
        self.config_path = self._first_host_dir() / "settings" / "cline_mcp_settings.json"
        self.skills_dir = None  # .cline/skills is project-scope (Phase 3)

    @staticmethod
    def _host_dirs() -> list[Path]:
        if sys.platform == "darwin":
            supp = Path.home() / "Library" / "Application Support"
        elif sys.platform == "win32":
            supp = Path.home() / "AppData" / "Roaming"
        else:
            supp = Path.home() / ".config"
        hosts = ["Code", "Code - Insiders", "VSCodium", "Cursor", "Windsurf"]
        return [supp / h / "globalStorage" / "saoudrizwan.claude-dev" for h in hosts]

    @classmethod
    def _first_host_dir(cls) -> Path:
        for d in cls._host_dirs():
            if d.exists():
                return d
        return cls._host_dirs()[0]

    def _entry(self, cmd: list[str]) -> dict:
        e = super()._entry(cmd)
        e["disabled"] = False
        return e


class GenericSkillIntegrator:
    """Fallback: install the skill to the cross-agent ~/.agents/skills dir."""

    id = "generic-skill"
    display_name = "Any agent (cross-agent skill)"

    def detect(self) -> object:
        from .base import Detection

        return Detection(True, "universal fallback")

    def plan(self, cmd: list[str]) -> list:
        from .base import Action

        return [Action("COPY_SKILL", str(Path.home() / ".agents" / "skills" / NAME))]

    def apply(self, cmd: list[str], dry_run: bool = False) -> object:
        from .base import InstallManifest, Result, install_skill

        if dry_run:
            return Result(True, "(dry run)")
        manifest = InstallManifest()
        action = install_skill(Path.home() / ".agents" / "skills" / NAME, manifest)
        return Result(True, action.detail, actions=[action])

    def verify(self) -> list:
        return [(True, "generic skill dir populated")]

    def remove(self) -> object:
        import shutil

        from .base import Result

        d = Path.home() / ".agents" / "skills" / NAME
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        return Result(True, "removed")
