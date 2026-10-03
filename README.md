# snapdec

**One install. Any machine. Any coding agent.** Fast, calibrated, *local* typed
decisions (classify / check / score / rank) exposed to every coding agent through
one shared MCP server + a portable Agent Skill.

> `snapdec` — "snap decision". The architecture/research document predates the
> rename and still uses the internal placeholder `sysone`
> ([SYSONE_ARCHITECTURE.md](SYSONE_ARCHITECTURE.md), rename ADR:
> [docs/adr/0007](docs/adr/0007-rename-snapdec.md)). Not affiliated with
> TypeSafe/Jev, Kev, or Laya.

Status: **Phase 1 (MVP) in development.** Backends live today: `tier0`
(deterministic, no model), `mock` (deterministic dev backend), `remote`
(any `/v1/systemone` server — hosted TypeSafe Jev, OpenRouter, your own
`kev.serve` / `laya-serve`). Managed local model provisioning (Laya ONNX/MLX,
Kev) lands in Phase 2.

## Install (dev, pre-release)

```bash
uv tool install -e .   # or: pipx install snapdec (once published)
```

## Quickstart

```bash
snapdec init            # hardware check → backend wizard → wires every agent found
snapdec doctor --live   # verify install, daemon, per-agent registration
```

The wizard (first run) is **one prompt, fully automatic**:

```
Decision backend — paste a key for hosted, or press Enter for free & local.

API key (Enter = free & local):
```

- **Paste any key** → provider auto-detected from the key format (OpenRouter /
  TypeSafe detected; OpenAI/Groq/Anthropic keys get a clear "not System One
  compatible — here's what to use" hint, never a silent misroute) → model
  auto-picked for your device with a **free-variant-first, paid-fallback**
  chain validated by a live canary call.
- **Press Enter** → snapdec auto-probes localhost for any running
  `/v1/systemone` server (`kev.serve`, `laya-serve`, …), takes the first that
  answers, and reads the model list from the server itself. Nothing found →
  exact commands to start one are printed, and Tier-0 (deterministic,
  zero-model) is configured so the tools still work.
- Keys live only in snapdec's own config (env-var reference or 0600 file) —
  **never** copied into agent configs (ADR-0006).

Non-interactive: `snapdec init --yes --api-key sk-or-…` (or
`--backend hosted:openrouter|local|tier0|mock` for explicit control).

## What agents get

| Tool | Tier | What it does |
|---|---|---|
| `project_facts` | 0 | Test/lint/typecheck/build commands, package manager, monorepo layout, CI — deterministic, zero model calls |
| `classify` | 1 | Label items from caller-defined classes, with calibrated probabilities |
| `check` | 1 | Yes/no questions about one piece of evidence (`yes \| no \| uncertain`) |
| `score` | 1 | Ordinal rating (severity/priority/risk), 2–10 levels |
| `rank` | 1 | Which candidates answer a query |

Every Tier-1 answer carries `decision: auto | review` — the model abstains
honestly; the host agent decides `review` items itself. Advisory only: never
used to approve destructive commands or authorize anything security-relevant.

## Supported agents

Claude Code · Codex · Cursor · OpenCode · Antigravity · Windsurf · VS Code
(Copilot) · Cline · any agent via the cross-agent `~/.agents/skills` dir.
CLI-first registration (`claude mcp add`, `codex mcp add`), config edits only as
backup-first, atomic, idempotent fallback. `snapdec uninstall` reverses exactly.

## Uninstall

```bash
snapdec uninstall             # reverses every integration, stops the daemon
snapdec uninstall --purge-models   # also removes all snapdec state
```

## Development

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest
```

Architecture, research findings, and the phase plan live in
[SYSONE_ARCHITECTURE.md](SYSONE_ARCHITECTURE.md). ADRs in `docs/adr/`.

License: Apache-2.0.
