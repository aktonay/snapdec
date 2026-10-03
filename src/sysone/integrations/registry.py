"""Integrator registry — order = display order in `sysone init`."""

from __future__ import annotations

from .agents_json import (
    AntigravityIntegrator,
    ClineIntegrator,
    CursorIntegrator,
    GenericSkillIntegrator,
    OpenCodeIntegrator,
    VsCodeIntegrator,
    WindsurfIntegrator,
)
from .claude_code import ClaudeCodeIntegrator
from .codex import CodexIntegrator

_ALL = [
    ClaudeCodeIntegrator,
    CodexIntegrator,
    CursorIntegrator,
    OpenCodeIntegrator,
    AntigravityIntegrator,
    WindsurfIntegrator,
    VsCodeIntegrator,
    ClineIntegrator,
    GenericSkillIntegrator,
]

ALL_INTEGRATORS = {cls.id: cls() for cls in _ALL}
