from __future__ import annotations

import json
from pathlib import Path

from snapdec._brand import __version__

ROOT = Path(__file__).resolve().parents[2]


def _server_json() -> dict:
    return json.loads((ROOT / "server.json").read_text(encoding="utf-8"))


def test_server_json_version_matches_brand():
    s = _server_json()
    assert s["version"] == __version__
    assert s["packages"][0]["version"] == __version__


def test_server_json_description_fits_registry_limit():
    assert len(_server_json()["description"]) <= 100


def test_server_json_name_matches_readme_marker():
    marker = next(
        line for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("<!-- mcp-name:"))
    assert _server_json()["name"] in marker
