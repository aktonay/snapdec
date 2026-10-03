from __future__ import annotations

from pathlib import Path

from sysone.integrations.patchers import append_block, json_merge, jsonc_merge, toml_merge


def test_json_merge_preserves_unknown_keys(tmp_path: Path):
    p = tmp_path / "mcp.json"
    p.write_text('{"mcpServers": {"other": {"command": "x"}}, "version": 5}')
    out = json_merge(p, {"mcpServers": {"sysone": {"command": "sysone"}}})
    assert out.wrote
    import json

    data = json.loads(p.read_text())
    assert data["mcpServers"]["other"]["command"] == "x"
    assert data["version"] == 5
    assert data["mcpServers"]["sysone"]["command"] == "sysone"
    assert list(data) == ["mcpServers", "version"]  # key order preserved


def test_json_merge_idempotent(tmp_path: Path):
    p = tmp_path / "mcp.json"
    p.write_text("{}")
    json_merge(p, {"mcpServers": {"sysone": {"command": "s"}}})
    first = p.read_text()
    out = json_merge(p, {"mcpServers": {"sysone": {"command": "s"}}})
    assert not out.wrote and p.read_text() == first


def test_json_merge_creates_backup(tmp_path: Path):
    p = tmp_path / "mcp.json"
    p.write_text('{"a": 1}')
    json_merge(p, {"mcpServers": {"sysone": {}}})
    baks = list(tmp_path.glob("mcp.json.bak-*"))
    assert len(baks) == 1 and baks[0].read_text() == '{"a": 1}'


def test_json_malformed_hands_off(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{not json!!")
    out = json_merge(p, {"mcpServers": {}})
    assert not out.wrote and out.reason and out.snippet
    assert p.read_text() == "{not json!!"  # untouched


def test_jsonc_with_comments_never_rewritten(tmp_path: Path):
    p = tmp_path / "opencode.jsonc"
    p.write_text('{\n  // my setup\n  "theme": "dark"\n}\n')
    out = jsonc_merge(p, {"mcp": {"sysone": {}}})
    assert not out.wrote and "comments" in out.snippet
    assert "// my setup" in p.read_text()  # intact


def test_jsonc_without_comments_writes(tmp_path: Path):
    p = tmp_path / "opencode.json"
    p.write_text('{"theme": "dark"}')
    out = jsonc_merge(p, {"mcp": {"sysone": {"type": "local"}}})
    assert out.wrote


def test_toml_merge_preserves_comments(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text('# user comment\nmodel = "gpt"\n\n[mcp_servers.existing]\ncommand = "x"\n')
    out = toml_merge(p, "mcp_servers.sysone", {"command": "sysone", "args": ["mcp"]})
    assert out.wrote
    text = p.read_text()
    assert "# user comment" in text
    assert "command = \"x\"" in text  # existing table intact
    assert "[mcp_servers.sysone]" in text


def test_toml_idempotent_and_malformed(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text("model = \"gpt\"\n")
    toml_merge(p, "mcp_servers.sysone", {"command": "sysone"})
    before = p.read_text()
    out = toml_merge(p, "mcp_servers.sysone", {"command": "sysone"})
    assert not out.wrote and p.read_text() == before
    bad = tmp_path / "bad.toml"
    bad.write_text("= broken [")
    out2 = toml_merge(bad, "a.b", {"c": 1})
    assert not out2.wrote and "hands off" in out2.reason


def test_append_block_roundtrip(tmp_path: Path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("existing content\n")
    append_block(p, "use sysone", "sysone")
    assert "sysone:begin" in p.read_text() and "existing content" in p.read_text()
    append_block(p, "", "sysone")  # empty block = remove
    text = p.read_text()
    assert "sysone:begin" not in text and "existing content" in text
