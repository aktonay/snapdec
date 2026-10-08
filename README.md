# ⚡ snapdec

<!-- mcp-name: io.github.aktonay/snapdec -->

<p align="center">
  <strong>Fast, Calibrated Micro-Decisions for AI Coding Agents</strong><br>
  <em>Offload high-volume classification, checks, scores, and ranking from frontier LLMs to sub-50ms local models.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/snapdec/"><img src="https://img.shields.io/pypi/v/snapdec.svg?color=blue" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/snapdec/"><img src="https://img.shields.io/pypi/pyversions/snapdec.svg" alt="Python Versions"></a>
  <a href="https://registry.modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP_Registry-listed-4a90d9?logo=anthropic" alt="MCP Registry Listed"></a>
  <a href="https://github.com/aktonay/snapdec/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/aktonay/snapdec/ci.yml?branch=main&label=CI" alt="CI Status"></a>
  <a href="https://github.com/aktonay/snapdec/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"></a>
  <a href="https://github.com/aktonay/snapdec"><img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey" alt="Platforms"></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/aktonay/snapdec/main/assets/snapdec-banner.jpg" alt="snapdec - Fast Micro-Decisions for Coding Agents | MCP Server" width="100%">
</p>

---

## 📌 What is snapdec?

**snapdec** (Snap Decisions) is a lightweight, zero-configuration **Model Context Protocol (MCP) server** and **Agent Skill** that gives AI coding agents a dedicated **System 1 fast-thinking engine**. 

Instead of burning thousands of tokens and 3–5 seconds of latency having frontier LLMs (Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro) deliberate over routine categorical choices, `snapdec` executes typed micro-decisions—**classify, check, score, rank**, and **deterministic project facts**—using specialized local models (Kev, Laya) or free hosted routers in **under 50 milliseconds**.

### 💡 Why Coding Agents Need Snapdec
Coding agents execute hundreds of micro-decisions during multi-turn workflows:
* *"Is this test error an environmental flake or a code bug?"*
* *"Which 3 files out of 30 in this git diff touch authentication?"*
* *"What severity level is this linter violation?"*
* *"Does this repo use uv, poetry, npm, pnpm, or cargo?"*

Sending these trivial questions into a 200,000-token context window bloats costs, slows down the agent loop, and wastes time. `snapdec` intercepts these tasks, processes them in parallel with calibrated confidence scores, and returns an honest `auto | review` recommendation.

---

## ✨ Key Features

- ⚡ **Sub-50ms Micro-Decisions**: Run classification and ranking in 5–50 ms locally on CPU, Apple Silicon (MLX), or CUDA GPU.
- 🎯 **Calibrated Probabilities & Fail-Closed Abstention**: Every decision includes exact confidence scores (`probabilities`) and a typed verdict (`auto | review`). If the model is uncertain, it safely abstains and defers to the host agent.
- 🛠️ **Tier-0 Deterministic Facts (0 Tokens)**: Instant, zero-token repository introspection (`project_facts`) detecting test runners, linters, package managers, monorepos, and CI setups.
- 💻 **Hardware-Aware Auto-Profiler**: `snapdec init` inspects your exact CPU, RAM, GPU, VRAM, and OS, presenting only the local models your machine can genuinely run.
- 🔌 **Zero-Config Agent Integration**: Automatically registers with **9+ coding agents** with atomic backups and 1-click clean uninstall:
  - Claude Code
  - Cursor
  - Windsurf
  - VS Code & GitHub Copilot
  - Codex CLI
  - Cline / Roo Code
  - OpenCode
  - Google Antigravity
- 🔋 **Always-On, Zero Idle Drain**: Lightweight stdio MCP shim starts in <1s. Daemon starts lazily on first tool call and automatically resurrects dead backends. Zero background battery drain when idle.
- 🔒 **100% Private & Local Loopback**: Local servers bind strictly to `127.0.0.1`. API keys are stored in user-owned state with restricted permissions (0600) and never leak to agent configs. **Zero telemetry.**
- 🔄 **Safe, Non-Intrusive Updates**: `snapdec update` checks PyPI with a 24-hour cache. Never installs silently or modifies agent files without user consent.

---

## 🚀 Quickstart (60 Seconds)

### 1. Install snapdec
Install using `uv` (recommended), `pipx`, or standard `pip`:

```bash
# Recommended: isolated tool installation via uv
uv tool install snapdec

# Or via pipx
pipx install snapdec

# Or standard python pip
pip install snapdec
```

### 2. Run the Interactive Setup Wizard
Run `snapdec init` to profile your system, choose your backend, and auto-wire all detected coding agents:

```bash
snapdec init
```

The wizard scans your hardware and displays an honest, benchmarked menu tailored to your machine:

```text
Recommended for this machine (13th Gen i5 · 16 GB RAM · Intel UHD · Windows 11)

  LOCAL — free · private · offline
    [1] Laya EN (421M)  —  DI ~0 zero-shot (specialize-first base)
        5–15 ms GPU/Apple · 50–450 ms CPU · setup: ~2 GB        (recommended)
    [2] Laya multilingual (322M)  —  DI ~0 zero-shot · 100+ languages
    [3] Decision 2.0 Eos 0.8B  —  card: JevArena 53.9 · transfer 50.3 (vllm-sr)
        setup: ~3 GB · best Decision 2.0 fit for this machine
        CPU: ~7 s/question (bench)                           [slow on CPU]
    [4] Decision 2.0 Kai 0.6B  —  card: JevArena 48.6 · smallest (~2 GB)
        CPU: ~6 s/question (bench)                           [slow on CPU]
    [5] Kev 0.8B  —  DI 23.3 · OOD acc 0.65
        40–80 ms CUDA · fast on Apple (MLX) · CPU: seconds/question
        setup: ~5 GB                                             [slow on CPU]
  HOSTED — API key · best accuracy
    [6] OpenRouter  —  free keys (openrouter.ai/keys) · typesafe/jev-router · Jev DI 54.0
    [7] TypeSafe Jev  —  native /v1/systemone · Jev DI 54.0 (best known) · paid per call
    [8] Other /v1/systemone URL

Choice [1]:
```

> **Headless / CI Mode**: You can also initialize non-interactively:
> ```bash
> snapdec init --yes --backend local             # Auto-select best local model
> snapdec init --yes --api-key sk-or-v1-xxxx     # Auto-detect provider & model
> ```

---

## 🔍 How It Works

```text
┌─────────────────────────────────────────────────────────────┐
│             Coding Agents (Claude Code, Cursor, ...)        │
└──────────────────────────────┬──────────────────────────────┘
                               │ stdio MCP (thin shim, <1s startup)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 snapdec daemon (127.0.0.1 IPC)              │
│       Lazy-start · Health check · Auto-resurrect            │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
    [ Local Inference Engine ]     [ Hosted System One API ]
    • Kev 0.8B / 4B / 9B / 27B     • OpenRouter (jev-router)
    • Laya EN / Multilingual       • TypeSafe Jev
    • Decision 2.0 (vllm-sr)       • Custom /v1/systemone
    • ONNX / PyTorch / MLX
```

Every response returned to the agent includes calibrated metadata and a discreet status footer:

```json
{
  "results": [
    {"id": "t1", "label": "bug", "p": 0.94, "decision": "auto"},
    {"id": "t2", "label": "infra", "p": 0.61, "decision": "review"}
  ],
  "summary": {
    "items": 2,
    "auto": 1,
    "review": 1
  },
  "status": "· snapdec 0.5.0 · kev-0.8b · 38 ms · 1/2 auto · ~210 tok offloaded"
}
```

### The `auto | review` Philosophy (Safe Abstention)
- **`decision: "auto"`**: The model's confidence exceeds the calibrated threshold. The agent can act immediately in batch without asking the user or second-guessing.
- **`decision: "review"`**: The model's confidence is below threshold or evidence is ambiguous. The agent falls back to inspecting the problem directly.
- **Advisory Only**: `snapdec` is strictly an advisory decision engine. It is never used to automatically approve destructive actions (deletions, pushes, migrations).

---

## 🧰 Available MCP Tools

When snapdec is registered, agents gain access to 6 specialized tools:

| Tool | Tier | Latency | Tokens | Description |
|:---|:---:|:---:|:---:|:---|
| **`project_facts`** | 0 | <1 ms | 0 | Instant inspection of test runner, linter, package manager, monorepo layout, and CI configuration. Fully deterministic. |
| **`classify`** | 1 | 15–50 ms | Offloaded | Multi-class categorizer. Takes a list of items and candidate classes, returning labels with calibrated probabilities. |
| **`check`** | 1 | 10–40 ms | Offloaded | Fast boolean verification (`yes \| no \| uncertain`) against provided evidence. |
| **`score`** | 1 | 15–45 ms | Offloaded | Ordinal rating on a calibrated scale of 2–10 levels (e.g. risk assessment, severity rating, priority). |
| **`rank`** | 1 | 20–60 ms | Offloaded | Evaluates candidates against a query, returning relevance ranking and best-match recommendations. |
| **`ask`** | 1 | 20–50 ms | Offloaded | Direct structured question answering over short context state. |

> **Parallel Fan-Out**: Multi-item requests are automatically fanned out concurrently in parallel batches so small-context local models never truncate or bottleneck on large collections.

---

## 💻 CLI Usage & Mirrors

All MCP tools have direct CLI counterparts for terminal workflows, shell scripts, and CI pipelines:

```bash
# Deterministic repository inspection (Tier 0)
snapdec project-facts .

# Categorize errors or logs from stdin (Tier 1)
echo '{"items":[{"id":"1","text":"ConnectionResetError during upload"}],
       "classes":{"network":"transient socket error","bug":"code bug"}}' \
  | snapdec classify --input -

# Diagnostic health check
snapdec doctor --live

# Update to latest version
snapdec update

# View hardware-gated model catalog
snapdec models

# Run local accuracy and latency benchmark suite
snapdec bench --backend mock
```

---

## 🤖 Supported Coding Agents

`snapdec init` and `snapdec agents add` automatically configure all installed agent environments:

| Agent | Config Path / Mechanism | Status |
|:---|:---|:---:|
| **Claude Code** | CLI integration (`claude mcp add`) | ✅ Auto-configured |
| **Cursor** | `~/.cursor/mcp.json` | ✅ Auto-configured |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` | ✅ Auto-configured |
| **VS Code / Copilot** | `.vscode/mcp.json` / user settings | ✅ Auto-configured |
| **Codex CLI** | `~/.codex/config.toml` | ✅ Auto-configured |
| **Cline / Roo Code** | `cline_mcp_settings.json` | ✅ Auto-configured |
| **OpenCode** | `~/.opencode/mcp.json` | ✅ Auto-configured |
| **Antigravity** | Workspace & user agent custom rules | ✅ Auto-configured |

To export standard configuration for any other MCP-compliant client:
```bash
snapdec agents print-snippet
```

---

## 📊 Models & Benchmarks

`snapdec` supports both local open weights and hosted router endpoints:

| Model | Parameters | Hardware / Runtime | Latency | Accuracy (DI / OOD) | Notes |
|:---|:---:|:---|:---:|:---:|:---|
| **Laya EN** | 421M | CPU / DirectML / Apple Silicon | 5–15 ms | Base zero-shot | Ultra-lightweight, 2 GB footprint |
| **Laya Multilingual** | 322M | CPU / DirectML / Apple Silicon | 5–15 ms | Base zero-shot | 100+ languages supported |
| **Kev 0.8B** | 0.8B | CUDA / Apple Silicon (MLX) | 40–80 ms | DI 23.3 · OOD 0.65 | Recommended for Apple Silicon & GPUs |
| **Kev 4B** | 4.0B | 16 GB+ VRAM GPU | 60–120 ms | DI 38.0 | High-accuracy local model |
| **Kev 9B** | 9.0B | 24 GB+ VRAM GPU | 80–180 ms | DI 41.0 | Heavyweight local specialist |
| **Kev 27B** | 27.0B | 80 GB+ GPU / 96GB+ Mac | 150–350 ms | DI 52.3 | Near-frontier decision intelligence |
| **Decision 2.0 Kai** | 0.6B | CPU (slow) / CUDA / Apple (CPU, slow) | ~5.8 s CPU · 4.9 ms GPU (card) | card: JevArena 48.6 (†) | Smallest of the family |
| **Decision 2.0 Eos** | 0.8B | CPU (slow) / CUDA / Apple (CPU, slow) | ~7.4 s CPU · 6.0 ms GPU (card) | card: JevArena 53.9 (†) | Starred on CPU/Windows; beats Kev-0.8B on card |
| **Decision 2.0 Sol** | 2B | CPU (slow) / CUDA / Apple (32 GB+) | not benched · 7.2 ms GPU (card) | card: JevArena 52.1 (†) | Fits 16 GB RAM, marked slow on CPU |
| **Decision 2.0 Nox** | 4B | CPU (very slow) / CUDA / Apple (32 GB+) | not benched · 12.9 ms GPU (card) | card: JevArena 63.6 (†) | Needs ≥20 GB RAM |
| **imajev 2B** | 2.2B | CPU (slow, 12 GB+ RAM) / Apple (MLX, 8 GB+) | p50 14.8 s / p95 35.1 s CPU | board: JevBench hard 60.4 · Img JevBench 68.72 #6 (‡) | Only variant a 16 GB PC runs |
| **imajev 4B** | 4.3B | CPU (very slow, 24 GB+) / Apple (MLX, 16 GB+) | bench pending | board: JevBench 67.37 #1 · Img 76.39 #1 · DecisionBench 79.65 #3 (‡) | Board #1 text decision model |
| **imajev 9B** | 9.4B | CPU (48 GB+) / Apple (MLX, 32 GB+) | bench pending | board: JevBench hard 69.4 (‡) | Heavyweight Qwen3.5 specialist |
| **TypeSafe Jev** | Hosted | Native `/v1/systemone` | ~120 ms | DI 54.0 (Reference) | Best known decision intelligence |
| **OpenRouter** | Hosted | `typesafe/jev-router` | ~150 ms | Jev DI 54.0 | Free API key tier available |

*DI (Decision Intelligence) benchmarks cited from the official Kev 1.0 test suite. Measured local performance available in [`docs/benchmarks/`](docs/benchmarks/).*

*(†) Decision 2.0 numbers are from the vendor's model cards (`vllm-sr`, 2026-10) on their own JevArena index — a different scale from the held-out breadth-v1 numbers above, so the two are never cross-compared (ADR-0008/0010). Measured CPU latency lives in [`docs/benchmarks/`](docs/benchmarks/). On Apple Silicon, Decision 2.0 runs via the plain CPU path (no MLX build yet; MPS unvalidated), so Kev 0.8B (MLX) stays the recommended fast local pick there.*

*(‡) imajev numbers are JevBench board standings (2026-09) and repo runs on their own indices — a third scale, never cross-compared with kev's breadth-v1 or the vllm-sr card (ADR-0008/0011). Measured CPU latency lives in [`docs/benchmarks/`](docs/benchmarks/). On Apple Silicon imajev runs a real MLX fast path (fp16), unlike Decision 2.0 there. Downloads show live byte + speed progress bars.*

---

## 🔒 Security, Privacy & Reliability

- **Strict Loopback Binding**: Local model servers bind only to `127.0.0.1`. No external ports are ever opened.
- **Protected Secrets**: API keys are saved with strict `0600` file permissions in `~/.local/state/snapdec/` or read from environment variables. They are **never written into agent configuration files**.
- **Fail-Closed Design (NFR-4)**: If a backend crashes, drops connection, or times out, snapdec returns a valid envelope with `decision: "review"`. It **never throws an unhandled exception** or interrupts your agent session.
- **Zero Telemetry**: No usage stats, prompts, code snippets, or user data are ever tracked or phoned home.

---

## 🛠️ CLI Command Reference

| Command | Description |
|:---|:---|
| `snapdec init` | Interactive system setup wizard (auto-detects hardware and agents). |
| `snapdec doctor` | Comprehensive health check of daemon, backend, and agent registrations. |
| `snapdec update` | Check PyPI and upgrade snapdec installation safely. |
| `snapdec daemon [start\|stop\|status\|logs]` | Manage the background decision daemon. |
| `snapdec agents [list\|add\|remove\|print-snippet]` | Manage coding agent integrations. |
| `snapdec models [--all]` | List all runnable models matching current hardware. |
| `snapdec bench [--backend mock]` | Run the decision accuracy and latency benchmark suite. |
| `snapdec project-facts [path]` | Deterministic repository fact extraction. |
| `snapdec classify --input -` | CLI classifier reading JSON from stdin. |
| `snapdec check --input -` | CLI verification reading JSON from stdin. |
| `snapdec score --input -` | CLI ordinal scoring tool reading JSON from stdin. |
| `snapdec rank --input -` | CLI ranker reading JSON from stdin. |
| `snapdec uninstall` | Cleanly reverses all agent integrations and removes configurations. |

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><strong>How does snapdec reduce coding agent token usage?</strong></summary>

Frontier LLMs incur input token costs for every turn in their conversation history. In agent loops, repeatedly passing long logs, diffs, and lists into a 200k context window to ask small classification or boolean questions consumes significant tokens and compute. `snapdec` offloads these discrete questions to a local model or fast router, returning only the concise answer and confidence score.
</details>

<details>
<summary><strong>Can snapdec run completely offline?</strong></summary>

Yes. When you choose a local model (such as Laya or Kev), all dependencies, weights, and runtimes run on your local machine on `127.0.0.1`. No internet connection is required after initial model download.
</details>

<details>
<summary><strong>What happens if the local daemon crashes?</strong></summary>

The MCP shim features built-in self-healing: if the daemon is stopped or crashes, the shim automatically re-spawns it on the next incoming tool call. If the backend fails to recover, it returns a safe `decision: "review"` envelope so the agent continues operating without crashing.
</details>

<details>
<summary><strong>How do I remove or uninstall snapdec?</strong></summary>

Simply run:
```bash
snapdec uninstall
```
This restores all agent configuration files from their original backups and cleans up registered skills.
</details>

---

## 📜 Architecture & Decisions

- Architecture Design: [SYSONE_ARCHITECTURE.md](SYSONE_ARCHITECTURE.md)
- Architectural Decision Records (ADRs):
  - [ADR-0001: Shim / Daemon Split](docs/adr/0001-shim-daemon-split.md)
  - [ADR-0002: Decision Tiers](docs/adr/0002-decision-tiers.md)
  - [ADR-0004: IPC Transport](docs/adr/0004-ipc-transport.md)
  - [ADR-0006: API Key Storage](docs/adr/0006-api-key-storage.md)
  - [ADR-0007: Rename Gate to snapdec](docs/adr/0007-rename-snapdec.md)
  - [ADR-0008: Kev 1.0 Refresh & Model Catalog](docs/adr/0008-kev-1-0-refresh.md)
  - [ADR-0009: Update Mechanism & Status Footer](docs/adr/0009-update-and-status.md)
  - [ADR-0010: Decision 2.0 as Third Local Backend](docs/adr/0010-decision2-backend.md)

---

## 📄 License

Distributed under the **Apache-2.0 License**. See [LICENSE](LICENSE) for details.

*snapdec routes to and credits [Kev](https://github.com/jaredpalmer/kev), [Laya](https://github.com/aktonay), [TypeSafe Jev](https://typesafe.com), the [vllm-sr](https://huggingface.co/vllm-sr) Decision 2.0 family, and the [imajev](https://github.com/mohit67890/imajev) family (pinned @ `ccf586d4`). Model weights are distributed under their respective Apache-2.0 licenses.*
