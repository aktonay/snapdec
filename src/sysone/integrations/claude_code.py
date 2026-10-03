"""Claude Code — CLI-first (§8.3 row 1).

`claude mcp add --scope user` writes ~/.claude.json (top-level
mcpServers); the file is rewritten frequently by Claude Code itself, so
racing it with a manual edit risks corruption. File edit is fallback
only. Skill dir: ~/.claude/skills/sysone/.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .._brand import NAME
from .base import (
    Action,
    Detection,
    InstallManifest,
    Result,
    atomic_write,
    backup_file,
    install_skill,
    load_json,
)
from .patchers import jsonc_merge


class ClaudeCodeIntegrator:
    id = "claude-code"
    display_name = "Claude Code"

    def _cli(self) -> str | None:
        return shutil.which("claude")

    def config_file(self) -> Path:
        return Path.home() / ".claude.json"

    def skills_dir(self) -> Path:
        return Path.home() / ".claude" / "skills" / NAME

    def detect(self) -> Detection:
        cli = self._cli()
        cfg = self.config_file()
        installed = bool(cli or cfg.exists())
        ev = []
        if cli:
            ev.append("claude CLI on PATH")
        if cfg.exists():
            ev.append(str(cfg))
        return Detection(installed, "; ".join(ev), config_paths=[str(cfg)])

    def plan(self, exe: str) -> list[Action]:
        cli = self._cli()
        if cli:
            return [
                Action("CLI", f"claude mcp add --scope user {NAME} -- {exe} mcp"),
                Action("COPY_SKILL", str(self.skills_dir())),
            ]
        return [
            Action("JSON_MERGE", f"mcpServers.{NAME} → {self.config_file()}"),
            Action("COPY_SKILL", str(self.skills_dir())),
        ]

    def apply(self, exe: str, dry_run: bool = False) -> Result:
        manifest = InstallManifest()
        cli = self._cli()
        actions: list[Action] = []
        snippets: list[str] = []
        if not dry_run:
            if cli:
                # flags BEFORE the `--` (§2.2); startup needs < 1 s so no timeout key
                cmd = [cli, "mcp", "add", "--scope", "user", NAME, "--", exe, "mcp"]
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if r.returncode == 0:
                        actions.append(Action("CLI", " ".join(cmd[:6]) + " …"))
                    else:
                        snippets.append(f"claude mcp add failed "
                                        f"(rc={r.returncode}): {r.stderr.strip()[:200]}")
                except (OSError, subprocess.TimeoutExpired) as e:
                    snippets.append(f"claude CLI error: {e}")
            if not cli or snippets:
                out = jsonc_merge(self.config_file(),
                                  {"mcpServers": {NAME: {"type": "stdio",
                                                         "command": exe,
                                                         "args": ["mcp"], "env": {}}}},
                                  manifest=manifest)
                actions.extend(out.actions)
                if out.snippet:
                    snippets.append(out.snippet)
            actions.append(install_skill(self.skills_dir(), manifest))
        return Result(True, "; ".join(a.detail for a in actions) or "(dry run)",
                      actions=actions, manual_snippet="\n\n".join(snippets))

    def verify(self) -> list[tuple[bool, str]]:
        cli = self._cli()
        if cli:
            try:
                r = subprocess.run([cli, "mcp", "get", NAME],
                                   capture_output=True, text=True, timeout=30)
                if r.returncode == 0 and NAME in (r.stdout + r.stderr):
                    return [(True, "Claude Code: registered (verified via CLI)")]
                return [(False, f"Claude Code: `claude mcp get {NAME}` not found")]
            except (OSError, subprocess.TimeoutExpired) as e:
                return [(False, f"Claude Code: CLI check failed ({e})")]
        data, err = load_json(self.config_file())
        if data is None:
            return [(False, f"Claude Code: {err}")]
        ok = NAME in (data.get("mcpServers") or {})
        return [(ok, f"Claude Code: {'registered' if ok else 'not registered'}")]

    def remove(self) -> Result:
        cli = self._cli()
        if cli:
            try:
                subprocess.run([cli, "mcp", "remove", "--scope", "user", NAME],
                               capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                pass
        cfg = self.config_file()
        if cfg.exists():
            data, err = load_json(cfg)
            if data is not None:
                servers = data.get("mcpServers")
                if isinstance(servers, dict) and NAME in servers:
                    backup_file(cfg)
                    del servers[NAME]
                    atomic_write(cfg, json.dumps(data, indent=2) + "\n")
        d = self.skills_dir()
        if d.exists():
            import shutil

            shutil.rmtree(d, ignore_errors=True)
        return Result(True, "removed")
