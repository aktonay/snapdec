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

The wizard (first run):

```
How should snapdec make decisions on this machine?   (13th Gen i5 · 16 GB · Windows)

  [1] Hosted — I have an API key        (text leaves this machine)
        a) TypeSafe Jev   b) OpenRouter   c) other /v1/systemone URL
  [2] Local — free, private             (Phase 1: point at your kev.serve / laya-serve URL)
        recommended for this machine: laya-multilingual via ONNX Runtime CPU (INT8)
  [3] Tier-0 only — no model             (deterministic project_facts)
  [4] Mock — deterministic dev backend
```

Keys live only in snapdec's own config (env-var reference or 0600 file) —
**never** copied into agent configs (ADR-006).

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
