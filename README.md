# snapdec

<!-- mcp-name: io.github.aktonay/snapdec -->

[![MCP Registry](https://img.shields.io/badge/MCP_Registry-listed-4a90d9)](https://registry.modelcontextprotocol.io/)
[![PyPI](https://img.shields.io/pypi/v/snapdec)](https://pypi.org/project/snapdec/)

**Snap decisions for coding agents.** One command, any machine, any agent:
fast, calibrated typed decisions (classify / check / score / rank) from a
local model or hosted API — exposed to every coding agent through one shared
MCP server plus a portable Agent Skill.

- **One prompt setup** — snapdec shows your PC spec and a menu of every backend
  your hardware can actually run, with honest accuracy stats. You choose.
- **Local = fully automatic** — pick a local model and snapdec creates a
  runtime venv, downloads the model, launches the server (127.0.0.1 only),
  and wires it into every coding agent it finds. No other steps.
- **Hosted = paste a key** — provider auto-detected from the key format, model
  auto-selected (free variant first), validated by a live canary call.
- **Honest by design** — every answer carries calibrated probabilities and an
  `auto | review` decision. Uncertain → the agent decides itself. Advisory
  only; never used to approve destructive actions.

## Install

```bash
uv tool install snapdec     # or: pipx install snapdec / pip install snapdec
snapdec init
```

Dev (from source): `uv venv && uv pip install -e ".[dev]" && uv run pytest`

## The first-run menu (real example, 16 GB laptop, no dGPU)

```
Recommended for this machine (13th Gen i5 · 16 GB RAM · Intel UHD · Windows 11)

  LOCAL — free · private · offline
    [1] Laya EN (421M)  —  DI ~0 zero-shot (specialize-first base)
        5–15 ms GPU/Apple · 50–450 ms CPU · setup: ~2 GB        (recommended)
    [2] Laya multilingual (322M)  —  DI ~0 zero-shot · 100+ languages
    [3] Kev 0.8B  —  DI 23.3 · OOD acc 0.65
        40–80 ms CUDA · fast on Apple (MLX) · CPU: seconds/question
        setup: ~5 GB                                             [slow on CPU]
  HOSTED — API key · best accuracy
    [4] OpenRouter  —  free keys (openrouter.ai/keys) · typesafe/jev-router · Jev DI 54.0 (best known)
    [5] TypeSafe Jev  —  native /v1/systemone · Jev DI 54.0 (best known) · paid per call
    [6] Other /v1/systemone URL

Choice [1]:
```

And on a Mac (M-series, 16 GB) the same wizard stars Kev 0.8B — validated
on all Apple Silicon via MLX, no "slow on CPU" flag there:

```
  LOCAL — free · private · offline
    [1] Kev 0.8B (0.8B)  —  DI 23.3 · OOD acc 0.65
        40–80 ms CUDA · fast on Apple (MLX) · setup: ~5 GB      (recommended)
    [2] Laya EN (421M)  —  DI ~0 zero-shot (specialize-first base)
    ...
```

Only what fits your hardware is listed — a machine without a 16 GB+ GPU
never sees Kev-4B (DI 38.0), without 24 GB never sees Kev-9B (DI 41.0),
and Kev-27B (DI 52.3, near-Jev) appears only on 80 GB+ boards or
96–128 GB Macs. Every listed option is genuinely runnable. Stats are
Kev 1.0 held-out numbers (breadth-v1 test, chance-corrected; Jev 54.0 is
the best known reference) from the [kev model cards](https://github.com/jaredpalmer/kev).

Picking `[3]` on the Windows machine above works — you get the honest
`[slow on CPU]` flag first. Freedom within your spec.

After you choose, snapdec automatically:

1. provisions the backend (local: venv + download + server; hosted: key
   validation + model canary),
2. registers its MCP server in **every coding agent it detects** (Claude
   Code, Codex, Cursor, OpenCode, Antigravity, Windsurf, VS Code, Cline —
   CLI-first, backup-first, exactly reversible),
3. installs the Agent Skill globally so every repo gets it,
4. starts the shared daemon and prints a live health check.

## What agents get

| Tool | Tier | What it does |
|---|---|---|
| `project_facts` | 0 | Test/lint/typecheck/build commands, package manager, monorepo layout, CI — deterministic, zero model calls |
| `classify` | 1 | Label items from caller-defined classes, with calibrated probabilities |
| `check` | 1 | Yes/no questions about one piece of evidence (`yes \| no \| uncertain`) |
| `score` | 1 | Ordinal rating (severity/priority/risk), 2–10 levels |
| `rank` | 1 | Which candidates answer a query |

Multi-item tools fan out one request per item (small-context backends can't
answer N items against one blob) and run the calls in parallel.

Example (CLI mirror of the MCP tool, real output from Laya on a CPU laptop):

```
$ echo '{"items":[
    {"id":"t1","text":"Tests failed: OSError network unreachable on runner"},
    {"id":"t2","text":"AssertionError: expected status 200, got 500"},
    {"id":"t3","text":"ModuleNotFoundError: No module named requests"}],
  "classes":{"infra":"network/runner problem","bug":"real code bug",
             "deps":"missing dependency"}}' | snapdec classify --input -

t1: bug    p=0.73  decision=review
t2: bug    p=0.94  decision=auto
t3: deps   p=0.61  decision=review
```

`auto` results can be acted on in bulk; `review` items go back to the host
agent — that abstention is the product.

## CLI

```
snapdec init                 # the wizard (above)
snapdec init --yes --api-key sk-or-…      # non-interactive, provider auto-detected
snapdec init --yes --backend local        # non-interactive managed local setup
snapdec doctor --live        # verify install, daemon, every agent registration
snapdec update               # upgrade when PyPI has a newer version
snapdec daemon start|stop|status|logs
snapdec agents list|add|remove|print-snippet   # integrations, all reversible
snapdec models [--all]       # hardware-gated catalog, honest stats
snapdec bench [--backend mock]  # accuracy/Brier/latency mini-suite
snapdec classify|check|score|rank --input -   # CLI mirrors of the tools
snapdec project-facts .      # tier-0 facts straight from the terminal
snapdec uninstall            # reverses every integration exactly
```

Every answer ends with a quiet status footer (what ran, latency, how much
text stayed off the host model):

```
· snapdec 0.4.0 · jaredpalmer/kev-0.8b · 38 ms · 7/12 auto · ~210 tok offloaded
```

Upgrades: `init`/`doctor` print a notice when PyPI has something newer
(cached 24 h); `snapdec update` upgrades (uv tool → pip → pipx) and asks
you to re-run `init` once to refresh the skill copy. Nothing installs
silently. The daemon is lazy — first tool call starts it, dead managed
backends resurrect on their own; no background services.

## Architecture (30 seconds)

```
agents (Claude Code, Codex, Cursor, …)
   │ stdio MCP (one thin shim per agent, <1 s start, no ML imports)
   ▼
snapdec daemon (one shared process, loopback+token IPC / UDS)
   ▼
backend: managed Laya (8901) · managed Kev (8902, pinned git SHA)
         · hosted /v1/systemone (OpenRouter, TypeSafe, any URL) · mock
```

Keys live only in snapdec's own state (env-var reference or 0600 file) —
never in agent configs. Local servers bind 127.0.0.1 only. No telemetry.

Full design doc with research citations: [SYSONE_ARCHITECTURE.md](SYSONE_ARCHITECTURE.md)
· decisions: [docs/adr/](docs/adr/)

## Status

Phase 1/2 complete for: tier-0, managed Laya + Kev (1.0, all four sizes)
provisioning, hosted backends, 9 agent integrations, MCP v2 shim + shared
daemon, `bench` mini-suite, MCP Registry listing (`io.github.aktonay/snapdec`).
Windows is verified on real hardware (managed Laya); macOS/Linux covered by
CI and follow the same paths. Honest gaps: Windows managed-kev 1.0 install
not re-verified on real hardware (torch is a big download); Kev-9B/27B on
Mac are upstream-unmeasured (labels say so); Laya zero-shot is weak (the
stats say so in the menu); calibration refit and micro-batching are Phase 4.
Measured claims live in [docs/benchmarks/](docs/benchmarks/).

## License

Apache-2.0. Not affiliated with TypeSafe/Jev, Kev, or Laya — snapdec routes
to them and credits them. Model licenses: Apache-2.0 (Kev, Laya).
