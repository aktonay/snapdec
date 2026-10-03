"""JSON / JSONC / TOML patchers with the §8.2 safety rules.

- JSON: parse → merge → dump (key order preserved by dict insertion).
- JSONC: if the file contains comments we DO NOT write — the caller gets
  a snippet to print (rule 4). No comment stripping on write, ever.
- TOML: tomlkit round-trip preserves comments and formatting.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit

from .base import Action, InstallManifest, atomic_write, backup_file, load_json, merge_dict

_COMMENT_RE = re.compile(r"^\s*(//|#|/\*)")


@dataclass
class PatchOutcome:
    wrote: bool
    actions: list[Action]
    snippet: str = ""  # non-empty → we refused to write; show this instead
    reason: str = ""


def json_merge(path: Path, updates: dict[str, Any], *,
               manifest: InstallManifest | None = None) -> PatchOutcome:
    """Merge `updates` into a JSON file. Existing keys win only if identical
    value semantics are respected by merge_dict; unknown keys preserved."""
    data, err = load_json(path)
    if data is None:
        return PatchOutcome(False, [], snippet=json.dumps(updates, indent=2),
                            reason=f"{path}: {err}")
    before = json.dumps(data, sort_keys=True)
    merge_dict(data, updates)
    after = json.dumps(data, sort_keys=True)
    actions: list[Action] = []
    if before != after:
        bak = backup_file(path) if path.exists() else None
        atomic_write(path, json.dumps(data, indent=2) + "\n")
        if manifest:
            manifest.record_file(path, bak)
        actions.append(Action("JSON_MERGE", str(path), target=str(path)))
    return PatchOutcome(before != after, actions)


def jsonc_merge(path: Path, updates: dict[str, Any], *,
                manifest: InstallManifest | None = None) -> PatchOutcome:
    """JSONC-aware merge. Commented files are never rewritten (rule 4)."""
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as e:
            return PatchOutcome(False, [], snippet=json.dumps(updates, indent=2),
                                reason=f"{path}: unreadable ({e})")
        has_comments = any(_COMMENT_RE.match(line) for line in text.splitlines())
        # also detect trailing // comments after values
        trailing = re.search(r'(?m):\s*"[^"]*"\s*//', text)
        if has_comments or trailing:
            snippet = (
                f"# {path} contains comments — sysone will not rewrite it.\n"
                f"# Merge this by hand (key 'mcp'/'mcpServers' level):\n"
                + json.dumps(updates, indent=2)
            )
            return PatchOutcome(False, [], snippet=snippet,
                                reason="jsonc-with-comments: hands off")
    return json_merge(path, updates, manifest=manifest)


def toml_merge(path: Path, table: str, value: dict[str, Any], *,
               manifest: InstallManifest | None = None) -> PatchOutcome:
    """tomlkit merge — preserves comments and formatting (rule 4)."""
    try:
        if path.exists():
            doc = tomlkit.parse(path.read_text(encoding="utf-8-sig"))
        else:
            doc = tomlkit.document()
    except (OSError, ValueError) as e:
        return PatchOutcome(False, [], snippet=_toml_snippet(table, value),
                            reason=f"{path}: parse failure ({e}) — hands off")
    cur: Any = doc
    for part in table.split("."):
        cur = cur.setdefault(part, tomlkit.table())
    changed = not (part_in(cur, value))
    if changed:
        for k, v in value.items():
            cur[k] = v
        bak = backup_file(path) if path.exists() else None
        atomic_write(path, tomlkit.dumps(doc))
        if manifest:
            manifest.record_file(path, bak)
    return PatchOutcome(changed, [Action("TOML_MERGE", f"[{table}]", target=str(path))]
                        if changed else [])


def part_in(table: Any, value: dict[str, Any]) -> bool:
    try:
        return all(table.get(k) == v for k, v in value.items())
    except AttributeError:
        return False


def _toml_snippet(table: str, value: dict[str, Any]) -> str:
    t = tomlkit.table()
    for k, v in value.items():
        t[k] = v
    return f"# merge by hand:\n{tomlkit.dumps({table: t})}"


# ---------------------------------------------------------------- skill


def append_block(path: Path, block: str, marker: str,
                 manifest: InstallManifest | None = None) -> PatchOutcome:
    """Managed sentinel block (opt-in nudge, §8.4). Reversible exactly."""
    begin, end = f"<!-- {marker}:begin -->", f"<!-- {marker}:end -->"
    try:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as e:
        return PatchOutcome(False, [], reason=f"{path}: unreadable ({e})")
    import re as _re

    text = _re.sub(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", "", text,
                   flags=_re.DOTALL).rstrip() + "\n"
    if block:
        text += f"\n{begin}\n{block}\n{end}\n"
    bak = backup_file(path) if path.exists() else None
    atomic_write(path, text)
    if manifest:
        manifest.record_file(path, bak)
    return PatchOutcome(True, [Action("APPEND_BLOCK", marker, target=str(path))])
