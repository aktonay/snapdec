"""Tier-0 `project_facts` — deterministic, zero-model, 100 % reliable (§4.3).

Reads the given path read-only and reports test/lint/typecheck/build
commands, package manager(s), monorepo layout and CI provider, each with
evidence file paths. Pure function of the directory contents.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- helpers


def _read_json(p: Path) -> dict[str, Any] | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text_head(p: Path, limit: int = 65536) -> str:
    try:
        with p.open("r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


# ---------------------------------------------------------------- python


def _python_facts(root: Path, facts: dict[str, Any], evidence: list[str]) -> None:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        if (root / "setup.py").exists() or (root / "setup.cfg").exists():
            evidence.append("setup.py/cfg")
        else:
            return
    text = _read_text_head(pyproject) if pyproject.exists() else ""
    if pyproject.exists():
        evidence.append(str(pyproject.relative_to(root)))
    # package manager
    pm = None
    if (root / "uv.lock").exists():
        pm = "uv"
    elif (root / "poetry.lock").exists():
        pm = "poetry"
    elif (root / "Pipfile.lock").exists():
        pm = "pipenv"
    elif text and "-m pip" in text:
        pm = "pip"
    if pm:
        facts["python_package_manager"] = pm
    # test runner: explicit config wins, then dependency hints
    runner = None
    if "[tool.pytest" in text or (root / "pytest.ini").exists() or (root / "conftest.py").exists():
        runner = "pytest"
    elif any(s in text.lower() for s in ("unittest", "nose2")):
        runner = "unittest"
    if runner == "pytest":
        facts["test_cmd"] = "uv run pytest" if pm == "uv" else "python -m pytest"
    elif runner == "unittest":
        facts["test_cmd"] = "python -m unittest discover"
    if "ruff" in text:
        facts["lint_cmd"] = "ruff check ."
        facts.setdefault("format_cmd", "ruff format .")
    if "mypy" in text:
        facts["typecheck_cmd"] = "mypy ."
    if "pyright" in text:
        facts["typecheck_cmd"] = "pyright"
    if "[build-system]" in text or (root / "setup.py").exists():
        facts["build_cmd"] = f"{pm} build" if pm in ("uv", "poetry") else "python -m build"
    facts.setdefault("languages", []).append("python")


# ---------------------------------------------------------------- node/TS


def _node_facts(root: Path, facts: dict[str, Any], evidence: list[str]) -> None:
    pkg_path = root / "package.json"
    pkg = _read_json(pkg_path) if pkg_path.exists() else None
    if pkg is None:
        return
    evidence.append(str(pkg_path.relative_to(root)))
    pm = None
    if (root / "pnpm-lock.yaml").exists() or (root / "pnpm-workspace.yaml").exists():
        pm = "pnpm"
    elif (root / "yarn.lock").exists():
        pm = "yarn"
    elif (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        pm = "bun"
    elif (root / "package-lock.json").exists():
        pm = "npm"
    run = pm or "npm"
    scripts = pkg.get("scripts", {}) or {}
    if "test" in scripts:
        facts["test_cmd"] = f"{run} test"
    if any(k in scripts for k in ("lint", "eslint")):
        facts["lint_cmd"] = f"{run} run lint"
    if "typecheck" in scripts or "tsc" in str(scripts.get("build", "")):
        facts["typecheck_cmd"] = (
            f"{run} run typecheck" if "typecheck" in scripts else "tsc --noEmit")
    if "build" in scripts:
        facts["build_cmd"] = f"{run} run build"
    if pm:
        facts["node_package_manager"] = pm
    facts.setdefault("languages", []).append(
        "typescript" if ("typescript" in str(pkg.get("devDependencies", {})) or
                         (root / "tsconfig.json").exists()) else "javascript"
    )


# ---------------------------------------------------------------- others


def _other_facts(root: Path, facts: dict[str, Any], evidence: list[str]) -> None:
    if (root / "Cargo.toml").exists():
        facts.setdefault("languages", []).append("rust")
        facts["build_cmd"] = "cargo build"
        facts.setdefault("test_cmd", "cargo test")
        facts.setdefault("lint_cmd", "cargo clippy")
        evidence.append("Cargo.toml")
    if (root / "go.mod").exists():
        facts.setdefault("languages", []).append("go")
        facts["build_cmd"] = "go build ./..."
        facts.setdefault("test_cmd", "go test ./...")
        evidence.append("go.mod")
    if (root / "pom.xml").exists():
        facts.setdefault("languages", []).append("java")
        facts["build_cmd"] = "mvn package"
        facts.setdefault("test_cmd", "mvn test")
        evidence.append("pom.xml")
    elif (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        facts.setdefault("languages", []).append("java")
        gradlew = "./gradlew" if (root / "gradlew").exists() else "gradle"
        facts["build_cmd"] = f"{gradlew} build"
        facts.setdefault("test_cmd", f"{gradlew} test")
        evidence.append("build.gradle[.kts]")
    if list(root.glob("*.csproj")) or list(root.glob("*.sln")):
        facts.setdefault("languages", []).append("csharp")
        facts["build_cmd"] = "dotnet build"
        facts.setdefault("test_cmd", "dotnet test")
        evidence.append("*.csproj")
    if (root / "Gemfile").exists():
        facts.setdefault("languages", []).append("ruby")
        facts.setdefault("test_cmd", "bundle exec rake")
        evidence.append("Gemfile")
    if (root / "composer.json").exists():
        facts.setdefault("languages", []).append("php")
        evidence.append("composer.json")


# ---------------------------------------------------------------- monorepo


def _monorepo_facts(root: Path, facts: dict[str, Any], evidence: list[str]) -> None:
    layout: list[str] = []
    pkg = _read_json(root / "package.json") or {}
    workspaces = pkg.get("workspaces")
    if workspaces or (root / "pnpm-workspace.yaml").exists():
        layout.append("node-workspaces")
        evidence.append("package.json workspaces / pnpm-workspace.yaml")
    if (root / "nx.json").exists():
        layout.append("nx")
        evidence.append("nx.json")
    if (root / "turbo.json").exists():
        layout.append("turborepo")
        evidence.append("turbo.json")
    cargo = _read_text_head(root / "Cargo.toml", 4096) if (root / "Cargo.toml").exists() else ""
    if "[workspace]" in cargo:
        layout.append("cargo-workspace")
        evidence.append("Cargo.toml [workspace]")
    if layout:
        facts["monorepo_layout"] = layout


def _ci_facts(root: Path, facts: dict[str, Any], evidence: list[str]) -> None:
    cis = {
        ".github/workflows": "github-actions",
        ".gitlab-ci.yml": "gitlab-ci",
        ".circleci": "circleci",
        "azure-pipelines.yml": "azure-pipelines",
        "Jenkinsfile": "jenkins",
        ".travis.yml": "travis",
    }
    found = [name for path, name in cis.items() if (root / path).exists()]
    if found:
        facts["ci_provider"] = found
        evidence.extend(found)


# ---------------------------------------------------------------- public


def project_facts(path: str | os.PathLike[str] = ".") -> dict[str, Any]:
    root = Path(path).resolve()
    facts: dict[str, Any] = {"languages": []}
    evidence: list[str] = []
    if not root.is_dir():
        return {"error": f"not a directory: {root}", "facts": {}, "evidence": []}
    _python_facts(root, facts, evidence)
    _node_facts(root, facts, evidence)
    _other_facts(root, facts, evidence)
    _monorepo_facts(root, facts, evidence)
    _ci_facts(root, facts, evidence)
    if not facts["languages"] and not facts.get("test_cmd"):
        facts["note"] = "no recognized project markers"
    return {
        "facts": facts,
        "evidence": evidence[:20],
        "confidence": "deterministic",
    }
