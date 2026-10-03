from __future__ import annotations

import json

from sysone.decisions.tier0.project_facts import project_facts


def test_python_uv_pytest(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\n[tool.pytest.ini_options]\n[tool.ruff]\n")
    (tmp_path / "uv.lock").write_text("version = 1\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    r = project_facts(tmp_path)
    f = r["facts"]
    assert f["python_package_manager"] == "uv"
    assert f["test_cmd"] == "uv run pytest"
    assert f["lint_cmd"] == "ruff check ."
    assert f["ci_provider"] == ["github-actions"]
    assert "python" in f["languages"]
    assert r["confidence"] == "deterministic"


def test_node_pnpm(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "scripts": {"test": "vitest", "build": "vite build", "lint": "eslint ."},
        "devDependencies": {"typescript": "^5"}}))
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    r = project_facts(tmp_path)["facts"]
    assert r["node_package_manager"] == "pnpm"
    assert r["test_cmd"] == "pnpm test"
    assert r["build_cmd"] == "pnpm run build"
    assert "typescript" in r["languages"]


def test_cargo_workspace(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[workspace]\nmembers = ['a']\n")
    r = project_facts(tmp_path)["facts"]
    assert r["test_cmd"] == "cargo test"
    assert "cargo-workspace" in r["monorepo_layout"]


def test_go(tmp_path):
    (tmp_path / "go.mod").write_text("module x\n")
    r = project_facts(tmp_path)["facts"]
    assert r["build_cmd"] == "go build ./..."


def test_no_false_csharp(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    r = project_facts(tmp_path)["facts"]
    assert "csharp" not in r.get("languages", [])


def test_missing_dir():
    r = project_facts("Z:/definitely/not/here")
    assert "error" in r
