"""Codex — CLI-first, TOML fallback via tomlkit (§8.3 row 2).

~/.codex/config.toml → [mcp_servers.sysone]; CODEX_HOME relocates the
directory (respected here). Comments preserved by tomlkit.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .._brand import NAME
from .base import Action, Detection, InstallManifest, Result, install_skill
from .patchers import toml_merge


class CodexIntegrator:
    id = "codex"
    display_name = "Codex"

    def _cli(self) -> str | None:
        return shutil.which("codex")

    def config_file(self) -> Path:
        return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"

    def skills_dir(self) -> Path:
        return Path.home() / ".agents" / "skills" / NAME

    def detect(self) -> Detection:
        cli = self._cli()
        cfg = self.config_file()
        installed = bool(cli or cfg.exists() or (Path.home() / ".codex").exists())
        ev = []
        if cli:
            ev.append("codex CLI on PATH")
        if cfg.exists():
            ev.append(str(cfg))
        return Detection(installed, "; ".join(ev), config_paths=[str(cfg)])

    def plan(self, exe: str) -> list[Action]:
        if self._cli():
            return [Action("CLI", f"codex mcp add {NAME} -- {exe} mcp"),
                    Action("COPY_SKILL", str(self.skills_dir()))]
        return [Action("TOML_MERGE", f"[mcp_servers.{NAME}] → {self.config_file()}"),
                Action("COPY_SKILL", str(self.skills_dir()))]

    def apply(self, exe: str, dry_run: bool = False) -> Result:
        manifest = InstallManifest()
        actions: list[Action] = []
        snippets: list[str] = []
        cli = self._cli()
        if not dry_run:
            if cli:
                try:
                    r = subprocess.run([cli, "mcp", "add", NAME, "--", exe, "mcp"],
                                       capture_output=True, text=True, timeout=30)
                    if r.returncode == 0:
                        actions.append(Action("CLI", f"codex mcp add {NAME}"))
                    else:
                        snippets.append(f"codex mcp add rc={r.returncode}: "
                                        f"{(r.stderr or r.stdout).strip()[:200]}")
                except (OSError, subprocess.TimeoutExpired) as e:
                    snippets.append(f"codex CLI error: {e}")
            if not cli or snippets:
                out = toml_merge(self.config_file(), f"mcp_servers.{NAME}",
                                 {"command": exe, "args": ["mcp"]}, manifest=manifest)
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
                    return [(True, "Codex: registered (verified via CLI)")]
            except (OSError, subprocess.TimeoutExpired):
                pass
        cfg = self.config_file()
        if not cfg.exists():
            return [(False, "Codex: config missing")]
        import tomlkit

        try:
            doc = tomlkit.parse(cfg.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return [(False, "Codex: config unreadable")]
        ok = NAME in (doc.get("mcp_servers") or {})
        return [(ok, f"Codex: {'registered' if ok else 'not registered'}")]

    def remove(self) -> Result:
        cli = self._cli()
        if cli:
            try:
                subprocess.run([cli, "mcp", "remove", NAME],
                               capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                pass
        cfg = self.config_file()
        if cfg.exists():
            import tomlkit

            try:
                doc = tomlkit.parse(cfg.read_text(encoding="utf-8-sig"))
                servers = doc.get("mcp_servers")
                if servers is not None and NAME in servers:
                    from .base import atomic_write, backup_file

                    backup_file(cfg)
                    del servers[NAME]
                    atomic_write(cfg, tomlkit.dumps(doc))
            except (OSError, ValueError):
                pass
        d = self.skills_dir()
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        return Result(True, "removed")
