from __future__ import annotations

from pathlib import Path

import pytest

from snapdec.integrations.agents_json import CursorIntegrator, OpenCodeIntegrator
from snapdec.integrations.claude_code import ClaudeCodeIntegrator


@pytest.fixture()
def no_cli(monkeypatch: pytest.MonkeyPatch):
    """Force the file-edit fallback path even where CLIs exist (§0.4:
    tests must never run `claude mcp add` against a real HOME)."""
    import snapdec.integrations.claude_code as cc
    import snapdec.integrations.codex as cx

    monkeypatch.setattr(cc, "shutil", type("S", (), {"which": staticmethod(lambda n: None)}))
    monkeypatch.setattr(cx, "shutil", type("S", (), {"which": staticmethod(lambda n: None)}))


def test_cursor_apply_verify_remove_cycle(tmp_home: Path, no_cli):
    integ = CursorIntegrator()
    assert not integ.detect().installed
    r = integ.apply(["C:/snapdec/snapdec.exe"])
    assert r.ok
    cfg = tmp_home / ".cursor" / "mcp.json"
    assert cfg.exists()
    assert all(ok for ok, _ in integ.verify())
    skill = tmp_home / ".cursor" / "skills" / "snapdec" / "SKILL.md"
    assert skill.exists() and "description:" in skill.read_text(encoding="utf-8")
    rr = integ.remove()
    assert rr.ok
    import json

    data = json.loads(cfg.read_text())
    assert "snapdec" not in data["mcpServers"]  # exact reversal
    assert not skill.exists()


def test_cursor_unknown_keys_preserved(tmp_home: Path, no_cli):
    integ = CursorIntegrator()
    cfg = tmp_home / ".cursor" / "mcp.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('{"mcpServers": {"mine": {"command": "x"}}, "editor.fontSize": 12}')
    integ.apply(["snapdec"])
    import json

    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["mine"]["command"] == "x"
    assert data["editor.fontSize"] == 12


def test_opencode_uses_array_command(tmp_home: Path, no_cli):
    integ = OpenCodeIntegrator()
    r = integ.apply(["/usr/local/bin/snapdec"])
    assert r.ok
    import json

    cfg = tmp_home / ".config" / "opencode" / "opencode.json"
    data = json.loads(cfg.read_text())
    entry = data["mcp"]["snapdec"]
    assert entry["command"] == ["/usr/local/bin/snapdec", "mcp"]
    assert entry["type"] == "local"


def test_claude_code_file_fallback(tmp_home: Path, no_cli):
    integ = ClaudeCodeIntegrator()
    r = integ.apply(["snapdec"])
    assert r.ok and not r.manual_snippet
    import json

    data = json.loads((tmp_home / ".claude.json").read_text())
    assert data["mcpServers"]["snapdec"]["args"] == ["mcp"]
    assert all(ok for ok, _ in integ.verify())
    assert (tmp_home / ".claude" / "skills" / "snapdec" / "SKILL.md").exists()
    integ.remove()
    data = json.loads((tmp_home / ".claude.json").read_text())
    assert "snapdec" not in data["mcpServers"]
