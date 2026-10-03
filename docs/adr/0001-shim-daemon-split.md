# ADR-0001: Thin MCP shim + one shared daemon

Date: 2026-10-03 · Status: accepted (implements §4.2)

## Context
Each agent spawns its own MCP stdio process. Loading a model per process
duplicates RAM/VRAM and risks startup timeouts (Codex ≈10 s ❓).

## Decision
Two processes: `sysone mcp` (shim: static tool list, validation, Tier-0,
forwards Tier-1 over IPC) and `sysone daemon` (loads the backend once,
serves `/v1/systemone`). Shim auto-spawns the daemon on first call.

## Consequences
- One model in RAM serves all agents; shim starts in < 1 s (no heavy imports).
- Two environments later (tool env + managed runtime venv) — version check +
  `sysone upgrade` path required (Phase 2).
- Verified live: shim cold call spawns daemon and returns an envelope
  (tests/contract/test_mcp_server.py::test_tier1_with_mock_daemon).
