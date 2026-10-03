# sysone — Local System One Decision Layer for Coding Agents
### Architecture, Research Findings & Agent-Executable Build Plan

| | |
|---|---|
| **Document status** | v1.0 — research snapshot **2026-10-03** |
| **Working name** | `sysone` (placeholder — see §1.4 "Rename gate"; **do not publish under this name until Phase 0 clears it**) |
| **Goal** | One install, any machine, any coding agent: fast, calibrated, *local* typed decisions via MCP + Agent Skill |
| **License (project)** | Apache-2.0 (recommended; see §14) |
| **Audience** | (a) the human owner, (b) the implementing coding agent (Antigravity / Claude Code / Codex / etc.) |

---

## 0. How the implementing agent must use this document

Read this section first. It overrides your defaults.

1. **Build in the phase order in §15.** Do not start Phase N+1 before Phase N's *Definition of Done* passes.
2. **Evidence legend** (used throughout):
   - ✅ **Verified** — confirmed from official docs/model cards/repos during research (2026-10-03).
   - ⚠️ **Reported** — single secondary source, or self-reported by a model author. Treat as a hypothesis; confirm with a spike.
   - ❓ **Unverified** — plausible but not confirmed. **You must verify by experiment** before relying on it, and record the result in `docs/spikes/`.
3. **The ecosystem is ~2–3 weeks old** (Jev launched 2026-09-15; Kev weights 2026-09-20; CLM-8B 2026-09-23). Model repos, Python-version constraints, and APIs are changing *daily*. **Pin everything by commit SHA / exact version.** Never write "latest" into a manifest.
4. **Never write to a real user's config files during development or CI.** All tests run under a temporary `HOME` / `XDG_*` / `APPDATA`. The only code allowed to touch real configs is the `integrations/` layer, executed via `sysone init` with user consent.
5. **Human gates** — STOP and ask the owner before: (a) publishing to PyPI/TestPyPI or the MCP Registry, (b) choosing the final project name, (c) adding any network call other than model download and the opt-in remote backend, (d) adding any telemetry, (e) accepting a model whose license is not OSI-approved.
6. **Every non-obvious decision gets an ADR** in `docs/adr/NNNN-title.md` (context → decision → consequences).
7. **Claims must be measured.** Do not write "20 ms" or "saves X% tokens" in README/docs unless produced by `sysone bench` on a named machine and committed to `docs/benchmarks/`.
8. Keep MCP tool descriptions **short** (they consume the host agent's context on every turn). Budget: ≤ 6 tools, ≤ 60 words per tool description.

---

## 1. Executive summary

### 1.1 What we are building
A cross-platform, open-source tool (`pip` / `uv tool install` / `uvx`) that:

1. **Detects the machine** (OS, CPU, RAM, Apple Silicon / NVIDIA / AMD / Intel GPU, NPU) and picks an inference profile.
2. **Downloads and provisions** the right local decision model + runtime automatically (consented, resumable, checksum-verified).
3. **Exposes fast typed decisions** (classify / check / score / rank) to any coding agent through **one shared MCP server** and a **portable Agent Skill**, so the skill is available in *every* repository.
4. **Auto-integrates** with Claude Code, Codex, Cursor, OpenCode, Antigravity, Windsurf, VS Code (Copilot), Cline, and legacy/forked Roo-family agents — preferring each agent's own CLI over editing its config files.
5. **Abstains honestly.** Every answer carries calibrated probabilities and an `auto | review` decision; when the model is unsure it tells the host agent to decide for itself.

### 1.2 What "System One" means here (✅)
A **System One / decision model** reads a *state* plus *typed questions* and returns a calibrated probability distribution in **one forward pass — no text generation**. Three primitives: `choice` (pick one option), `noul` (yes/no, P(yes)), `score` (ordinal scale). The de-facto wire contract is TypeSafe's `POST /v1/systemone`, which open models (Kev, others) and several gateways (OpenRouter, Opper, Telnyx, LLM Gateway, VLM Run) replicate.

### 1.3 The three models in your brief — what they really are (✅ unless marked)

| Model | Architecture | Size | Runtime reality | Honest quality signal |
|---|---|---|---|---|
| **Kev-0.8B** (Jared Palmer, Apache-2.0) | LoRA (r=16) + pointer head on **Qwen3.5-0.8B-Base** (hybrid Gated-DeltaNet) | ~0.8B | Needs `transformers>=5.17`, `peft>=0.21`; **Python 3.12/3.13**; **fast only on CUDA + `flash-linear-attention`**; DeltaNet kernels have no MPS path (~0.33 s for 5 questions, bf16, M5) | In-distribution acc 0.825; **out-of-domain 0.652**; coverage@≤5 % error only **0.23**. ⚠️ Decision Index 0.2 (chance-corrected, 40 benchmarks): Kev-0.8B **13.26** vs Kev-4B 31.31, Kev-9B 35.41, Jev 51.67 |
| **Laya** (Convai Innovations, Apache-2.0) | **ModernBERT-large** encoder + decision head (EN 421M, 512 ctx); **mmBERT-base** (multilingual 322M, 1024 ctx); *typed-decisions* checkpoint | 322–421M | Encoder → ONNX/CoreML/MLX friendly. Community ports: ONNX (`tozp/laya-onnx`), **laya-mlx** (⚠️ 7–14 ms, M3 Max), **laya-coreml** (⚠️ ~5 ms), **edgejev** (⚠️ ONNX INT8, ~15.6 ms/question, 4-core CPU). T4: 32.8–39.5 ms ✅. CPU: ⚠️ 193–464 ms | **0.766 acc only after training on the benchmark's own split; zero-shot typed-decisions = 0.362** (random 0.318). Model card: *"a fast base to specialise, not a zero-shot decision engine."* Raw ECE 0.466 → 0.081 with per-type temperature refit |
| **CLM-v0.1-8B** (Contrastive-LM, Apache-2.0) | **Frozen Qwen3-8B** encoder + 2 small projection heads (state/action), contrastive (InfoNCE) | 8B encoder | **Linux + NVIDIA + vLLM** (pooling server on Qwen3-8B) **plus** `clm-serve`; default 2048-token limit; heads are encoder-locked. It **scores candidates you supply** — it does not invent them | ⚠️ 16.5 ms vs Jev 149.8 ms in a game demo. Coding verifier numbers (DeepSWE 81.6 %, Terminal-Bench 2.1 87.6 %) are **fine-tuned heads, self-reported, not zero-shot** |

**Other candidates to evaluate in the bake-off (⚠️/❓):** *Von* (ModernBERT-large 395M; CUDA/ROCm/MPS/CPU; self-reported 71.5 % macro on a 49-task OOD set), *OpenDecider* (400M; **license listed as "Custom" on one tracker vs Apache-2.0 in the author's post — verify before use**), *jeff* (400M GLiFormer + ONNX), *Kev-4B / Kev-8B (Qwen3, attention-only; recommended for low latency on Apple Silicon) / Kev-9B*, *Qwen3.5-OneForward* (zero-shot logits readout), *tinyjev*.

### 1.4 Rename gate (⚠️ blocking before publication)
- **`agent-s1` is a bad name.** "Agent S / S1 / S2 / S3" is **Simular AI's** computer-use agent framework (`simular-ai/Agent-S`, PyPI `gui-agents`). It will cause search/SEO confusion and possible trademark friction.
- Also avoid "Jev" / "TypeSafe" in the name (their trademarks; every community project here carries a "not affiliated" disclaimer). "System One" is used generically by the community, but do not imply affiliation.
- **Phase 0 task:** check availability of 8–10 candidates on PyPI, GitHub, npm and the MCP Registry namespace, then ask the owner to choose. All code must read the name from **one constant** (`src/sysone/_brand.py`) plus `pyproject.toml`, so a rename is a single commit. Do **not** use `reflex` (taken, large existing project).

### 1.5 Strategic reality check (read before investing)
The idea is **not novel anymore** — within weeks of Jev's launch there are already: `jev-code` (one-command setup for Claude Code/Codex/Pi/OpenCode, hosted Jev), `jev-mcp` ×4 (one supports local Kev), `jev-use`, `jev-guard`, `save-token-jev`, `jev-router`, `fast-jev-compaction`, `pi-jev` and more (⚠️ per community "awesome" lists). **Therefore the differentiators must be:**

| Differentiator | Why it matters | Prior art gap |
|---|---|---|
| **Local-first, no API key, no per-call cost** | Privacy; zero marginal cost; works offline | Most integrations call hosted Jev |
| **Hardware-aware auto-provisioning** (CPU / Apple / CUDA / DirectML / server) | Your explicit requirement; makes local models usable by non-experts | Existing local servers need manual setup |
| **Broad agent coverage via one shared daemon** | One model in RAM serves all agents | Per-agent MCP processes duplicate models |
| **Tier-0 deterministic tools** (`project_facts`) | Answers "pytest or npm test?" with 100 % reliability and *zero* model calls | Not offered by Jev wrappers |
| **Coding-specific eval + (later) fine-tuned `-code` heads** | The base models are weak out-of-domain; coding decisions *are* out-of-domain | No one publishes a coding-decision benchmark |
| **Python / `uvx` distribution + MCP Registry listing** | Matches the Python-first ML ecosystem | Most are Node/Rust/Go |

Interoperate, don't fork-war: speak the `/v1/systemone` contract so users can point `sysone` at hosted Jev, `kev.serve`, or any compatible server; credit and link prior art; consider upstreaming fixes.

### 1.6 Honest value model (what actually saves tokens)
A tool call costs the host agent tokens too (schema in context + call + result). Savings are real **only when the decision replaces a large read/reasoning step**:

| Situation | Frontier-model cost | Right tier |
|---|---|---|
| "Which test runner?" | ~50 tokens of reasoning | **Tier 0** (read `pyproject.toml`/`package.json`) — no model at all |
| "Which of these 40 CI failures are infra flakes?" | Reading 40 logs = thousands of tokens | **Tier 1** model, `classify` |
| "Which 5 of 300 files are relevant to this issue?" | Reading many files | **Tier 1** `rank` |
| "Is this shell command destructive?" | Small, but safety-critical | Tier 0 rules + Tier 1 as *advisory only*, never as authorization |
| Open-ended design/debug reasoning | — | **Tier 2** (host frontier model) |

→ The product's value is a **router with abstention**, not "replace the LLM". Success must be shown with the A/B harness in §12.

---

## 2. Research findings that change the original blueprint

### 2.1 Corrections to the draft architecture you provided

| # | Draft said | Reality (evidence) | Required change |
|---|---|---|---|
| 1 | Claude Code MCP config at `~/.claude/settings.json` | ✅ User-scope MCP servers live in **`~/.claude.json`**; the supported way is **`claude mcp add --scope user`**. `settings.json` holds permissions/hooks. A reported issue (anthropics/claude-code #16728) shows `--scope user` semantics have had bugs → verify with `claude mcp get` | Use the CLI first; JSON edit only as fallback; `doctor` must verify |
| 2 | OpenCode at `~/.opencode/config.json`, `mcpServers` key | ✅ `~/.config/opencode/opencode.json` (or `.jsonc`), key **`mcp`**, entries `{"type":"local","command":[...array...],"enabled":true,"environment":{}}` | New integrator; must handle **JSONC comments** |
| 3 | Only JSON configs | ✅ **Codex uses TOML**: `~/.codex/config.toml` → `[mcp_servers.<name>]` (+ `codex mcp add`); `CODEX_HOME` relocates; project `.codex/config.toml` loads only for trusted projects | TOML editor that preserves comments (`tomlkit`) |
| 4 | Roo Code is a first-class target; Roo path used `cline_mcp_settings.json` | ✅ Roo Code's extension was **shut down & archived 2026-05-15** (forks: ZooCode, Kilo Code; maintainers recommend Cline). Roo's file is `mcp_settings.json` (not `cline_…`) | Roo = **legacy best-effort**; Cline = first-class; verify fork extension IDs |
| 5 | `uvx agent-s1 init` registers `uvx agent-s1 mcp` in every agent | ❓ `uvx` envs are ephemeral/cache-bound; GUI-launched editors often lack `uv` on `PATH`; cold `uvx` start may exceed agents' MCP startup timeouts | Register an **absolute path** to a persistently installed `sysone` (via `uv tool install`); `uvx` only for trial |
| 6 | `from mcp.server.fastmcp import FastMCP`, `mcp>=1.2.0` | ✅ **MCP Python SDK v2.0.0 is stable (2026-07-28)**; `pip install mcp` now installs 2.x; **`FastMCP` → `MCPServer`**; spec revision **2026-07-28** (stateless, no handshake; *servers can no longer call the client*); v1 is security-fix-only | Depend on `mcp>=2,<3`; use v2 API (verify import path in docs); no reliance on server→client calls (roots/elicitation) |
| 7 | Hardware rule: VRAM ≥ 2 GB → Kev-0.8B; CPU → Laya ONNX | ✅ Kev needs `transformers>=5.17`, Python 3.12/3.13, `fla` for speed; ✅ Laya zero-shot ≈ random on typed decisions | Profile table in §5 is benchmark-driven, not VRAM-only |
| 8 | "Sub-millisecond" in one place, "~20 ms" in another | Neither is substantiated for these models (published: tens of ms GPU; hundreds of ms CPU/unfused) | Remove; measure |
| 9 | `fast_verify` returns **PASS if score > 0.70** | Unsafe semantics: a 0.8B model "passing" a diff will be over-trusted | `check` returns `yes / no / uncertain`; **never** "approved"; skill forbids use for security/destructive authorization |
| 10 | One MCP server process per agent, model loaded in each | Each agent spawns its own stdio server → N copies of the model | **Thin shim + one shared daemon** (§4) |
| 11 | `torch.cuda.is_available()` for detection | Base install has no torch; importing it to probe is slow and conflicts | Probe with `nvidia-smi`, `sysctl`, `rocminfo`, PowerShell/CIM — no ML imports |
| 12 | `fastapi`/`uvicorn`/`onnxruntime` in base deps | ORT variants (`onnxruntime`, `-gpu`, `-directml`, `-openvino`, `-migraphx`) **conflict**; torch is GBs | Base = tiny; heavy deps live in a **managed runtime venv** |
| 13 | "Deterministic" decisions | Model outputs are probabilistic | Deterministic guarantees come from **Tier 0**; models are advisory with abstention |
| 14 | Agents: Claude Code, OpenCode, Roo, Cline, Antigravity | Missing Codex, Cursor, Windsurf, VS Code native; **Gemini CLI deprecated** (replaced by Antigravity CLI, effective 2026-06-18) | Support matrix in §8 |

### 2.2 Verified integration facts (✅ unless marked)

| Agent | MCP config | Skills dir (Agent Skills / `SKILL.md`) | Notes |
|---|---|---|---|
| **Claude Code** | `claude mcp add --scope user …` → `~/.claude.json`; project `.mcp.json` (needs trust approval) | `~/.claude/skills/<name>/` | `-s user` must precede `--`. Tool names: `mcp__<server>__<tool>`. Plugin marketplace route exists |
| **Codex** (CLI/IDE/desktop share config) | `codex mcp add <name> -- <cmd>` → `~/.codex/config.toml` `[mcp_servers.<name>]` | `~/.codex/skills/` and/or `~/.agents/skills/` ❓ (sources differ; one reports a feature flag `[features] skills = true`) | ❓ default MCP startup timeout is short (≈10 s) → shim must start in < 1 s |
| **Cursor** | `~/.cursor/mcp.json` (`mcpServers`); per-project `.cursor/mcp.json`; **restart required** | `~/.cursor/skills/` | Remote field `url` |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` (global only); remote field `serverUrl`; supports `${env:VAR}` | `.windsurf/skills/` ⚠️ | Cursor-format configs silently fail for remote servers |
| **OpenCode** | `~/.config/opencode/opencode.json(c)`; project `opencode.json`/`.opencode/opencode.json`; `opencode mcp add` is interactive | `~/.config/opencode/skills/`, also reads `~/.agents/skills/` | Loaded at startup; restart |
| **Antigravity** (IDE + CLI) | `~/.gemini/config/mcp_config.json` (shared, documented by Google/Microsoft); workspace `.agents/mcp_config.json`; ⚠️ CLI-specific `~/.gemini/antigravity-cli/mcp_config.json` reported | Documented `~/.gemini/antigravity/skills/` but ⚠️ a community report says tools don't read it → **verify empirically**; project `.agents/skills/` | Key `mcpServers`, remote `serverUrl`; **Streamable HTTP only (no SSE)**; MCP read at startup; own per-tool allow-list prompts |
| **Gemini CLI** | `~/.gemini/settings.json` | `.gemini/skills/` | **Deprecated** for free/Pro/Ultra since 2026-06-18 → legacy, optional |
| **VS Code (Copilot agent)** | `<User>/mcp.json` (mac `~/Library/Application Support/Code/User/`, Linux `~/.config/Code/User/`, Win `%APPDATA%\Code\User\`) or `.vscode/mcp.json`; key **`servers`**, each entry has **`type`** | `.github/skills/` ⚠️ | WSL/remote: config lives in `~/.vscode-server/data/User/` |
| **Cline** | `<hostUser>/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`; entries add `disabled`, `autoApprove` | `.cline/skills/` ⚠️ | `<hostUser>` varies: `Code`, `Code - Insiders`, VSCodium, **Cursor, Windsurf, Antigravity** (all VS Code forks) |
| **Roo Code (legacy)** | `<hostUser>/globalStorage/rooveterinaryinc.roo-cline/settings/mcp_settings.json`; project `.roo/mcp.json` | `.roo/skills/` ⚠️ | **Discontinued 2026-05-15.** Best-effort only; add ZooCode/Kilo after verifying their IDs ❓ |
| **Pi** | No MCP client (native extension API) | `~/.agents/skills/` | Phase 4 optional |
| **Generic** | Print a copy-paste snippet | **`~/.agents/skills/`** (cross-agent convention) and `npx skills add <owner>/<repo>` (skills.sh CLI supports 40+ agents) | Fallback for everything else |

### 2.3 Distribution facts (✅)
- **MCP Registry** (`registry.modelcontextprotocol.io`): publish with `mcp-publisher` (`init`, `validate`, `login github|github-oidc`, `publish`). For **PyPI** packages the registry verifies ownership by finding an **`mcp-name: io.github.<user>/<name>`** line in the README **as published on PyPI** (PyPI captures `long_description` at upload — the marker must be in the *released* version). `description` ≤ **100 chars**. The package version must already exist on PyPI. Only `pypi.org` is supported. `server.json` version must match `pyproject.toml` (keep in sync by test).
- **Kev is not on PyPI** (⚠️ none found): install is `git clone` + `uv sync --extra serve`. **PyPI rejects packages that declare direct-URL (git) dependencies** → the Kev runtime must be provisioned by `sysone init` at runtime (e.g., `uv pip install "kev @ git+https://github.com/jaredpalmer/kev@<SHA>"` or a pinned codeload tarball), **not** as `[project.dependencies]`.
- **Laya gotcha (✅):** `laya.load()` can hang when TensorFlow is installed (transformers probes TF → abseil deadlock). Runtime env must set `USE_TF=0` / `TRANSFORMERS_NO_TF=1` (verify exact var) and not install TF.
- **ONNX Runtime (✅):** the ROCm EP is deprecated (use MIGraphX); Windows GPU = DirectML; macOS default wheel exposes CoreML; Intel = OpenVINO (separate wheel, extra DLL handling on Windows); NVIDIA = `onnxruntime-gpu` (CUDA 12/13 variants). **Variants are mutually exclusive in one environment.**
- **Agent Skills** (`SKILL.md` + YAML frontmatter) is an open standard (agentskills.io) honored by Claude Code, Codex, Cursor, OpenCode, Cline and 40+ tools; **skills auto-activate from their `description`**.

---

## 3. Requirements

### 3.1 Functional
| ID | Requirement |
|---|---|
| FR-1 | `sysone init` performs: detect hardware → **backend choice wizard (§9.1: hosted key vs local vs Tier-0 only)** → show plan & sizes → consent → provision runtime (local only) → download models (local only) → integrate agents → install skill → start daemon → live smoke test → print summary. Flags: `--yes --dry-run --agents a,b --project --backend hosted:typesafe\|hosted:openrouter\|hosted:custom\|local\|tier0 --api-key-env VAR --profile <id> --offline --no-models --remote-url <u>` |
| FR-2 | Works on macOS (arm64 **and** Intel), Linux (x86_64, arm64), Windows (x86_64; arm64 best-effort), WSL2, and inside dev containers |
| FR-3 | Hardware profiles from small laptop (CPU) → Apple Silicon (M1–M5, Mac mini) → NVIDIA consumer → server GPU → *no capable hardware* (Tier 0 + optional remote) |
| FR-4 | **One shared daemon** serves all agents; models loaded once; auto-start on first call; idle shutdown |
| FR-5 | **MCP server (stdio)** exposes ≤ 6 tools (§7). Starts in < 1 s even when models are not ready |
| FR-6 | **Agent Skill** installed globally so every repo gets it; optional project-scope install |
| FR-7 | Integrations are **idempotent, reversible, backed-up, dry-runnable**; `sysone uninstall` restores configs exactly |
| FR-8 | `sysone doctor [--live] [--report]` diagnoses install, per-agent registration, daemon, model, latency; `--report` emits a **redacted** JSON for GitHub issues |
| FR-9 | Backends are pluggable behind one interface; a **model manifest** (data, not code) lists models/profiles |
| FR-10 | Optional **remote backend** speaking `/v1/systemone` (hosted Jev, OpenRouter, `kev.serve`, team server) |
| FR-11 | `sysone bench` measures latency, accuracy, calibration, memory, and A/B token savings |
| FR-12 | Upgrade path: `sysone upgrade` updates shim, runtime, manifest; pinned revisions preserved |

### 3.2 Non-functional
| ID | Requirement |
|---|---|
| NFR-1 | **Privacy:** local mode sends nothing off-machine except model downloads. **No telemetry** by default (any future telemetry is opt-in, anonymous, documented) |
| NFR-2 | **Latency targets (to be validated, not promised):** shim cold start < 500 ms; warm `classify` p95 < 150 ms on profiles P2–P6; CPU profile p95 < 600 ms |
| NFR-3 | **Footprint:** base wheel < 2 MB, base deps ≤ 8; heavy deps only in runtime venv; idle daemon frees memory after timeout |
| NFR-4 | **Safety:** fail-closed — any error, timeout, truncation, or low confidence → `decision:"review"` and a reason; never raises into the host agent |
| NFR-5 | **Reproducibility:** pinned model revisions + file SHA-256; pinned runtime constraints file |
| NFR-6 | **Portability:** never assume shell, PATH, or `uv` presence in GUI-launched agents; use absolute paths |
| NFR-7 | **Observability:** structured logs in the state dir with rotation; `sysone logs` |
| NFR-8 | **Accessibility of contribution:** adding an agent integrator or a model must take < 1 day for an outside contributor (guides + templates in §14) |

### 3.3 Non-goals (v1)
Not a general chat model; not a replacement for the frontier model; no GUI app; no cloud service operated by us; no fine-tuning UI (CLI/doc only); no automatic *approval* of risky actions.

---

## 4. Architecture

### 4.1 System diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Coding agents (each spawns its own stdio MCP process)                        │
│  Claude Code · Codex · Cursor · OpenCode · Antigravity · Windsurf · VS Code   │
│  Cline · (Roo/forks) · any MCP client      + Agent Skill in ~/.agents/skills  │
└───────────────┬──────────────────────────────────────────────────────────────┘
                │ MCP over stdio  (starts < 1 s, imports almost nothing)
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  sysone MCP shim   (`sysone mcp`)  — runs in the lightweight tool env         │
│   • static tool list  • input validation  • Tier-0 tools (project_facts)       │
│   • connects to daemon (UDS / loopback+token); auto-spawns it if absent        │
│   • if backend not ready → returns {decision:"review", reason:"warming|…"}     │
└───────────────┬──────────────────────────────────────────────────────────────┘
                │ local IPC (System One wire contract: POST /v1/systemone)
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  sysone daemon  (`sysone daemon`) — runs inside the MANAGED RUNTIME VENV      │
│   router · micro-batcher · truncation/chunking · calibration & policy          │
│   lifecycle (lock file, idle timeout, health, logs)                           │
│                         │                                                      │
│     ┌───────────────────┼───────────────────────────────────────────────┐     │
│     ▼                   ▼                    ▼                ▼         ▼     │
│  laya-onnx          laya-mlx /          kev (torch/CUDA   clm-vllm     remote  │
│  (CPU/DML/CUDA/     laya-coreml         or MLX; via        (Linux+     System  │
│   OpenVINO)         (Apple Silicon)     kev.serve)         NVIDIA)     One URL │
└──────────────────────────────────────────────────────────────────────────────┘
        ▲ models: HF Hub, pinned SHA, SHA-256 verified, cached once
        ▲ control plane: `sysone init | doctor | upgrade | uninstall | bench`
```

### 4.2 Why a thin shim + shared daemon (ADR-001)
- Each agent launches its **own** MCP stdio process. Loading a 0.4–4 B model per process wastes RAM/VRAM and adds seconds of cold start (Kev reports a ~10 s one-time CUDA kernel compile ✅).
- Agents enforce MCP **startup timeouts** (❓ Codex ≈10 s). The shim must answer `initialize`/`tools/list` instantly with static metadata.
- Dependency isolation: Kev needs Python 3.12/3.13 + `transformers>=5.17`; the user's default Python may be 3.9 or 3.14; ORT variants conflict. A **managed runtime venv** (created by `uv` with a pinned Python) removes all of this.
- Consequence: two environments (tool env + runtime env). Mitigation: same distribution, different extras; shim verifies `runtime_version == shim_version` and offers `sysone upgrade`.

### 4.3 Decision tiers (ADR-002)

| Tier | What | When | Example |
|---|---|---|---|
| **0 — deterministic** | Pure code, no model | Answer is derivable from files/rules | `project_facts`: test runner, package manager, lint/format/typecheck commands, monorepo layout, CI provider |
| **1 — local decision model** | Calibrated System One backend | Fuzzy classification/ranking over text | Triage 40 CI failures; rank 300 files vs an issue; classify an error |
| **1b — remote System One** | Same contract, remote endpoint | No capable hardware, or user opts in | Hosted Jev via OpenRouter; team GPU server |
| **2 — host agent** | The frontier model in the agent | `decision:"review"` | Anything uncertain, truncated, or safety-relevant |

### 4.4 Process & IPC (ADR-004)
- **Daemon API = the System One wire contract** (`POST /v1/systemone`, `GET /v1/models`, `GET /healthz`) so backends are interchangeable and `kev.serve` can be used **unchanged** as a managed subprocess in Phase 1.
- **Transport:** Unix domain socket on macOS/Linux (`$XDG_RUNTIME_DIR` or `~/.local/state/sysone/daemon.sock`, mode 0600); loopback TCP on a random port + 256-bit bearer token in a 0600 file on Windows. Never bind non-loopback unless `--serve-team` is explicit and authenticated.
- **Single instance:** lock file (`filelock`); state file records PID, port/socket, version, backend, started_at.
- **Lifecycle:** lazy start by shim → warm-up (kernel compile, a canary request) → `ready`. Idle timeout default 30 min. `sysone daemon status|start|stop|restart|logs`. Crash → shim retries once → returns `review` with reason.
- **Concurrency:** per-backend async queue with micro-batching (collect up to 5–10 ms or N requests); one forward pass per batched group; request timeout default 5 s (configurable).

### 4.5 Canonical internal types (pydantic) — keep identical to the wire contract
```
SystemOneRequest { model?, state: str | object | list, questions: { name: Question } }
Question  { type: "choice"|"noul"|"score", instructions: str,
            criteria?: { option: description } | [level descriptions (2..10)] }
Answer    { type, choice?|noul?|score?, probabilities?, confidence?, legend? }
SystemOneResponse { answers: { name: Answer }, usage?, model?, ... }
```
`choice` ≤ 255 options; `score` 2–10 ordered levels (✅ per LLM Gateway docs). `kev.serve` exposes each checkpoint as model `kev-latest` (✅).

### 4.6 State sizing, truncation, chunking (critical for coding inputs)
Small models have small windows (✅ Laya EN 512 / multilingual & typed 1024; Kev trained ≤ 7,552 tokens; CLM default 2048). Coding inputs (stack traces, diffs, logs) routinely exceed this.
- **Never silently truncate.** If input > budget: apply a strategy, set `truncated:true`, add a warning, and **cap confidence** (force `decision:"review"` unless the question class is configured as truncation-safe).
- Strategies: `head_tail`; `error_focus` (keep error/exception/traceback lines ± context, drop passing/noise lines); `diff_hunks` (per-hunk fan-out, aggregate with max-risk); `symbol_summary` for files (path + signatures, not bodies).
- **Fan-out:** for `classify(items[])` on small-context backends, send **one request per item** and let the micro-batcher fuse them into one forward pass; on large-context backends (≥ 4k) pack items into one state.

### 4.7 Calibration & policy (ADR-005)
- Ship **per-(model, primitive)** temperature (✅ Kev stores one in `head.pt`; Laya's card shows per-type temperature refit drops mean ECE 0.466 → 0.081).
- Decision policy (defaults, tuned by Phase-2/4 evals): `auto` iff `probability ≥ auto_accept (0.85)` **and** `margin ≥ min_margin (0.5)` **and** not truncated **and** backend healthy; otherwise `review`. Thresholds overridable per call and per task class; **safety-class questions use asymmetric thresholds** (bias toward `review`).
- `sysone calibrate --data labeled.jsonl` fits temperature + thresholds on the user's own labels (Phase 4).

---

## 5. Hardware detection & runtime provisioning

### 5.1 Probes (no ML imports — ADR-003)
| Signal | macOS | Linux | Windows |
|---|---|---|---|
| OS/arch | `platform`, `uname -m` | same | `platform`, `PROCESSOR_ARCHITECTURE` |
| CPU model & flags | `sysctl -n machdep.cpu.brand_string`, `hw.optional.*`; **Rosetta**: `sysctl -n sysctl.proc_translated` (warn: x86 Python on Apple Silicon) | `/proc/cpuinfo`, `lscpu -J` (AVX2/AVX-512/AMX/NEON) | `Get-CimInstance Win32_Processor` |
| RAM / unified memory | `sysctl -n hw.memsize` | `/proc/meminfo`, **cgroup limits** (containers) | `Win32_ComputerSystem.TotalPhysicalMemory` |
| Apple chip / model | `system_profiler SPHardwareDataType -json`, `sysctl hw.model` (identifies Mac mini etc.) | — | — |
| NVIDIA | — (none on modern Macs) | `nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader,nounits` | same; **WSL2 also exposes `nvidia-smi`** |
| AMD | — | `rocminfo`, `rocm-smi --json`, `/sys/class/drm` | PowerShell `Win32_VideoController` |
| Intel iGPU/NPU | — | `/sys/class/drm`, `lspci`; OpenVINO device list (after install) | `Win32_VideoController`; ⚠️ NPU via OpenVINO/QNN |
| Disk free | cache dir | cache dir | cache dir |
| Network | proxy env (`HTTPS_PROXY`), `HF_ENDPOINT`, `HF_HUB_OFFLINE` | same | same |

⚠️ **Windows trap:** `Win32_VideoController.AdapterRAM` is a 32-bit field capped at 4 GB — prefer `nvidia-smi` or DXGI for VRAM. ❓ Windows-ARM64 and Intel-Mac (x86_64) wheel availability for torch/ORT is limited → fall back to ONNX-CPU or Tier 0/remote; verify per platform in Phase 0.

Output: a `HardwareReport` dataclass (JSON-serializable, redactable) used by `init`, `doctor --report`, and tests (fixtures of real command outputs under `tests/fixtures/hardware/`; target ≥ 30 fixtures incl. M1/M2/M3/M4/M5, Mac mini, Intel Mac, RTX 3050/4060/4090, A100/H100, AMD RX 7000, Intel Core Ultra, Snapdragon X, WSL2, Docker with cgroup limits).

### 5.2 Profile selection (initial — **to be replaced by Phase-2/4 bake-off results**)
Selection rule: **choose the smallest model that meets the accuracy/coverage bar on the coding eval (§12), subject to the latency budget — not the biggest model that fits.**

| Profile | Trigger | Runtime | Initial default model | Notes |
|---|---|---|---|---|
| **P0 `tier0`** | RAM < 4 GB, unsupported platform, or user opt-out | none | — | Tier-0 tools only (+ optional `--remote-url`) |
| **P1 `cpu`** | Any x86_64/arm64 CPU, ≥ 4 GB free RAM | ONNX Runtime CPU (INT8) | Laya-multilingual 322M or Laya-EN 421M (or Von/jeff if bake-off wins) | ⚠️ 193–464 ms unquantized; INT8 ⚠️ ~15 ms/question — **measure** |
| **P2 `apple`** | Apple Silicon, ≥ 8 GB unified | **MLX** (laya-mlx) or **CoreML** (laya-coreml, ANE) | Laya (MLX/CoreML) | ⚠️ 5–14 ms on M3 Max. Kev-0.8B is slow on MPS (✅); prefer Kev-8B (Qwen3, attention-only) or Kev via MLX path if wanted |
| **P3 `windows-gpu`** | Windows + DX12 GPU (AMD/Intel/NVIDIA) | ONNX Runtime **DirectML** (sequential exec, no memory-pattern — required) | Laya | NPU (OpenVINO/QNN) = later |
| **P4 `cuda-small`** | NVIDIA ≥ 4 GB VRAM | torch (bf16/fp16) + `flash-linear-attention`, or ORT-CUDA | **Kev-0.8B** and/or Laya | Kev-0.8B OOD acc is modest (✅ 0.65) → bake-off decides vs Laya/Von |
| **P5 `cuda-mid`** | NVIDIA 12–24 GB | torch | **Kev-4B** (✅ OOD 0.797; ⚠️ ~70–80 ms on RTX 4500 Ada after a ~10 s compile) | Optionally keep 0.8B as a fast tier |
| **P6 `server`** | Linux + NVIDIA ≥ 24 GB, or team server | torch / **vLLM** | **Kev-9B** (⚠️ ~17 GB) and/or **CLM-8B** (needs Qwen3-8B pooling server + `clm-serve`; candidates supplied by caller) | Optional `--serve-team` (authenticated, off by default) |
| **R `remote`** | `--remote-url` / user choice | HTTPS | Any `/v1/systemone` server | Redaction on; clearly labeled non-local |

### 5.3 Managed runtime environment (ADR-003)
- Location: `platformdirs.user_data_dir("sysone")/runtime/<profile>-<hash>/` (venv created with `uv venv --python 3.13` (3.12 fallback) — **uv-managed Python so the user's Python version is irrelevant**).
- Installed by `sysone init` via `uv pip install` using a shipped **constraints file** per profile (pinned versions; verify every pin on PyPI at implementation time). Exactly **one** ORT variant per environment.
- Torch index selection from detected driver: CPU index for CPU-only Linux (avoid multi-GB CUDA wheels), CUDA 12.x/13 index per driver capability; macOS default wheels.
- Git-sourced pieces (Kev) provisioned by the installer from a **pinned SHA** (codeload tarball preferred over `git clone` — no `git` dependency). Spike S2 decides whether to run Kev as `kev.serve` subprocess (Phase 1–2) or vendor a minimal Apache-2.0 loader (later).
- Env vars set for the daemon: `USE_TF=0`/`TRANSFORMERS_NO_TF=1` (❓ verify), `TOKENIZERS_PARALLELISM=false`, `HF_HUB_DISABLE_TELEMETRY=1`, thread caps.
- **Ephemeral-run guard:** if `init` detects it is running from a `uvx` cache env (`sys.prefix` under uv's cache), it first runs `uv tool install sysone==<this version>` (or `pipx`/`pip --user` fallback) and re-execs from the persistent path, so registered absolute paths remain valid.

### 5.4 Model download & cache
- `huggingface_hub.snapshot_download(repo_id, revision=<commit SHA>, allow_patterns=…)`; resumable; progress bars; respects `HF_HOME`/`HF_ENDPOINT`/proxies/`HF_HUB_OFFLINE`. **Reuse the HF cache** (users may already hold Qwen3.5-0.8B-Base).
- Pre-flight: free-disk check, size summary, license display, **explicit consent for > 500 MB** (`--yes` bypasses).
- Verify SHA-256 per file against the manifest; refuse on mismatch.
- **Security:** never `trust_remote_code=True`; prefer `safetensors`. Kev's `head.pt` is a torch pickle → load with `weights_only=True` (❓ verify it loads) or convert once to safetensors at pin time and publish the converted artifact with a hash.
- Offline: `--offline` uses cache only; `doctor` reports what's missing.

### 5.5 Model manifest schema (data, versioned, validated by JSON Schema in CI)
```yaml
- id: laya-multilingual-onnx-int8
  family: laya
  source: { hf_repo: <repo>, revision: <40-char sha>, files: [{path, sha256, bytes}] }
  license: Apache-2.0            # CI fails on non-OSI licenses unless allow-listed by owner
  runtime: onnx                  # onnx | mlx | coreml | torch | vllm-pooling | remote
  platforms: [linux-x86_64, linux-arm64, darwin-arm64, win-x86_64]
  min_ram_gb: 2
  min_vram_gb: 0
  context_tokens: 1024
  primitives: [choice, noul, score]
  calibration: { temperature: { choice: 1.0, noul: 1.0, score: 1.0 } }   # replaced by fitted values
  thresholds: { auto_accept: 0.85, min_margin: 0.5 }
  status: experimental           # experimental | stable
  provenance: { converted_by: community|us, notes: "..." }
```
Community ports (ONNX/MLX/CoreML) are **third-party artifacts**: pin SHAs, review conversion scripts, re-run parity tests (argmax agreement vs. reference PyTorch on a fixed suite; laya-mlx reports 63/63 argmax parity ✅ — require the same bar).

---

## 6. Backend interface

```python
class Backend(Protocol):
    id: str
    capabilities: frozenset[Primitive]          # choice | noul | score | rank
    max_state_tokens: int
    async def load(self) -> None: ...           # may take seconds; daemon reports `warming`
    async def system_one(self, req: SystemOneRequest) -> SystemOneResponse: ...
    async def rank(self, query: str, candidates: Sequence[Candidate]) -> RankResponse: ...  # optional; default via noul fan-out
    def health(self) -> Health: ...             # ready|warming|degraded|failed + device + memory
    async def close(self) -> None: ...
```
Adapters: `mock` (deterministic, for tests), `remote_systemone` (httpx; works with `kev.serve`, hosted Jev, OpenRouter, Opper, Telnyx), `kev_serve` (managed subprocess), `laya_onnx`, `laya_mlx`, `laya_coreml`, `clm_vllm`. New models = new adapter **or just a manifest entry** if they already speak `/v1/systemone`.

**CLM note:** it scores *supplied candidates* (planner/retriever must provide them). Map it to `rank` and `choice`-with-candidates; do not expose it for open `noul` questions unless its server supports them.

---

## 7. MCP server specification

Server name: `sysone`. Transport: stdio. **No stdout writes except protocol** (log to file/stderr). Built on **MCP Python SDK v2** (`mcp>=2,<3`; ✅ `FastMCP` renamed `MCPServer`, first-class `Client`, in-memory client for tests — confirm exact import paths in https://py.sdk.modelcontextprotocol.io/). Because spec 2026-07-28 removes server→client calls, **tools take all context as arguments** (e.g., `project_facts(path=…)`).

### 7.1 Tools (≤ 6; terse descriptions; all side-effect-free)
| Tool | Tier | Purpose | Input (essentials) | Output |
|---|---|---|---|---|
| `project_facts` | 0 | Detect test/lint/typecheck/build commands, package manager(s), monorepo layout, CI provider — with evidence file paths | `path` | `{facts:{…}, evidence:[…], confidence:"deterministic"}` |
| `classify` | 1 | Label each item from caller-defined classes | `items[{id,text}]`, `classes{label:desc}`, `instructions?` | per-item `label, probability, margin, probabilities, decision` |
| `check` | 1 | Yes/no questions about one piece of evidence | `evidence`, `checks{name:question}` | per-check `verdict: yes|no|uncertain, probability, decision` |
| `score` | 1 | Ordinal rating (severity/priority/risk) | `items[]`, `levels[2..10]` | `score, nearest_level, confidence, decision` |
| `rank` | 1 | Which candidates answer a query | `query`, `candidates[{id,text}]`, `top_k?` | sorted relevance, `any_relevant`, `decision` |
| `ask` | 1 | Raw System One passthrough (mixed question types) | `state`, `questions{}` | raw answers |

Pre-approval: all tools are pure functions of their arguments (`project_facts` reads the given path read-only), so recommend auto-approval where the host supports it — **offered during `init`, off unless the user consents**.

### 7.2 Decision envelope (every Tier-1 response)
```json
{
  "results": [{
    "id": "t1", "label": "infrastructure", "probability": 0.93, "margin": 0.88,
    "confidence": 0.90, "decision": "auto",
    "probabilities": {"infrastructure": 0.93, "assertion_bug": 0.05, "other": 0.02}
  }],
  "summary": {"items": 1, "auto": 1, "review": 0},
  "policy": {"auto_accept": 0.85, "min_margin": 0.5, "calibrated": true},
  "backend": {"name": "laya-mlx", "model": "…@<sha8>", "device": "apple-m4", "latency_ms": 12},
  "truncated": false,
  "warnings": []
}
```
Failure shape (never throw): `{"results":[], "decision":"review", "reason":"warming|timeout|no_backend|oversize|error", "hint":"…"}`.

### 7.3 Prompt-injection posture
Tier-1 inputs are untrusted repo/log text. Outputs are **enums + numbers** (low injection surface to the host), but the *classifier itself* can be swayed by adversarial text. Hence: advisory-only semantics, `check` has no "approve", safety questions use asymmetric thresholds, and the skill forbids using results to authorize destructive/secret-touching/network-egress actions.

---

## 8. Agent integration layer

### 8.1 Integrator contract (`integrations/base.py`)
```python
class Integrator(Protocol):
    id: str; display_name: str
    def detect(self, env) -> Detection                  # installed? version? config paths? evidence
    def plan(self, ctx) -> list[Action]                 # pure; used by --dry-run
    def apply(self, ctx) -> Result                      # idempotent
    def verify(self, ctx) -> list[Check]                # re-read config / call agent CLI to confirm
    def remove(self, ctx) -> Result                     # exact reversal from install manifest
```
`Action` kinds: `CLI(cmd)`, `JSON_MERGE(path, pointer, value)`, `JSONC_PATCH(path, …)`, `TOML_MERGE(path, table, value)`, `COPY_SKILL(dest)`, `APPEND_BLOCK(path, marker_id, text)`.

### 8.2 Safety rules for touching other tools' files (hard requirements)
1. **CLI-first.** If the agent ships a CLI (`claude mcp add`, `codex mcp add`), use it — it handles locking/format (Claude Code rewrites `~/.claude.json` frequently; racing it risks corruption). Fall back to file edit only if the CLI is missing or fails.
2. **Backup** before first modification: `<file>.bak-<UTC timestamp>` (never overwrite an older backup).
3. **Atomic write:** temp file in same dir + `os.replace`; preserve permissions/ownership (`~/.claude.json` is 0600).
4. **Preserve everything else:** unknown keys, key order, **comments** (JSONC for OpenCode/VS Code; TOML via `tomlkit`). If a file has comments and no safe patcher applies → **do not write**; print the exact snippet + path instead.
5. **Parse failure = hands off.** Malformed config is reported, never "repaired" (the draft's `except: data = {}` would have *wiped users' configs* — forbidden).
6. **Idempotent:** identical entry → no-op; different existing `sysone` entry → update only our key.
7. **Install manifest** at `<state>/installed.json` records every file touched, backup path, and the inserted value hash → `uninstall` reverses precisely and refuses to remove edited-by-user entries without `--force`.
8. **Absolute command path** resolved at install time (`shutil.which("sysone")` → fallback `sys.executable -m sysone`). Quote paths with spaces (Windows). No `cmd /c` wrappers needed for a real `.exe`.
9. **Scopes:** global by default; `--project` writes project-level config/skill and prints a reminder to **commit only non-secret files**.
10. **WSL / remote:** run integrators in the environment where the agent's server runs (detect `WSL_DISTRO_NAME`, `~/.vscode-server`); for Windows-side editors targeting WSL, print guidance rather than guessing.
11. After changes: print "**Restart <agent>**" (Cursor, Antigravity, OpenCode, Cline load MCP only at startup ✅).

### 8.3 Per-agent plan (initial; each row requires a Phase-0 spike with evidence)
| Agent | Primary action | Fallback | Skill destination | Verify |
|---|---|---|---|---|
| Claude Code | `claude mcp add --scope user sysone -- <abs> mcp` | edit `~/.claude.json` top-level `mcpServers` | `~/.claude/skills/sysone/` | `claude mcp get sysone` |
| Codex | `codex mcp add sysone -- <abs> mcp` | `tomlkit` edit `~/.codex/config.toml` | `~/.agents/skills/sysone/` (+ `~/.codex/skills/` if needed ❓) | `codex mcp get sysone` / `list --json` |
| Cursor | JSON merge `~/.cursor/mcp.json` | — | `~/.cursor/skills/sysone/` | re-read; warn restart |
| OpenCode | JSONC-safe merge into `~/.config/opencode/opencode.json(c)` (`mcp.sysone`) | print snippet | `~/.config/opencode/skills/sysone/` | `opencode mcp list` |
| Antigravity | JSON merge `~/.gemini/config/mcp_config.json` | also CLI-specific path if present ❓ | try `~/.gemini/antigravity/skills/`; else project `.agents/skills/` ❓ | re-read; manual UI check |
| Windsurf | JSON merge `~/.codeium/windsurf/mcp_config.json` | — | `.windsurf/skills/` (project) ⚠️ | re-read |
| VS Code | JSONC merge `<User>/mcp.json` (`servers.sysone` with `type:"stdio"`) | `.vscode/mcp.json` | `.github/skills/` ⚠️ | re-read |
| Cline | JSON merge `…/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` for **every detected host editor dir** | — | `.cline/skills/` ⚠️ | re-read |
| Roo / ZooCode / Kilo (legacy) | same as Cline with their extension IDs (**verify**) | — | — | best-effort, flagged "unmaintained" |
| Generic | print snippet | — | `~/.agents/skills/sysone/` | — |

### 8.4 The Skill (what makes it "active in any repo")
- Installed **globally** to each agent's user skills dir (and `~/.agents/skills/`), so it is available in every repository. **Activation is the agent's decision from the `description`** → write the description with concrete trigger phrases (CI/test failure triage, ranking many files/candidates, classifying errors/logs, choosing test/lint commands, scoring severity).
- Content (≤ 500 lines, progressive disclosure): *when to use / not use*; **Policy**: call `project_facts` first for command/layout questions; use `classify/check/score/rank` for ≥ ~5 items or fuzzy labeling; **act only on `auto`**, decide `review` items yourself; **never** use for security-sensitive approvals, destructive commands, secrets, or network-egress authorization; if `reason` ≠ none, proceed without it; mention in the final answer when a model decision drove an action. `references/` holds tool contracts and recipes (CI triage, file picking, error classification, diff-vs-description).
- **Optional "nudge" (opt-in `--nudge`)**: a 3-line managed block (sentinel markers `<!-- sysone:begin -->…<!-- sysone:end -->`) appended to global instruction files — `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.config/opencode/AGENTS.md`, `~/.gemini/GEMINI.md` — improving activation reliability. Removed cleanly on uninstall.
- **Optional Claude Code hooks** (❓ verify schema against current docs): `SessionStart` hook running `sysone daemon warm --quiet` to pre-warm models; and `permissions.allow: ["mcp__sysone__*"]` in `settings.json` *only if the user opts into auto-approval*.
- Also ship as a **Claude Code plugin marketplace** entry (`.claude-plugin/marketplace.json` bundling skill + MCP) and via `npx skills add <owner>/<repo> --skill sysone`.

---

## 9. CLI specification (`sysone`, Typer + Rich)

| Command | Behavior |
|---|---|
| `sysone init [flags]` | Full flow (FR-1). Interactive TUI summary; `--yes` for CI. Idempotent |
| `sysone mcp` | Run the stdio MCP shim (what agents launch) |
| `sysone daemon start|stop|status|restart|warm|logs` | Daemon control |
| `sysone doctor [--live] [--report] [--agent X]` | Checks: install path, Python/uv, hardware, profile, models present+hash, daemon, per-agent registration **re-verified via the agent's own CLI**, canary decision + latency. `--report` = redacted JSON (no usernames/paths/hostnames) |
| `sysone models list|pull|remove|verify|use <id>` | Manage models/profile |
| `sysone agents list|add <id>|remove <id>|print <id>` | Manage integrations; `print` outputs the snippet |
| `sysone project-facts [path]` | Tier-0 from the terminal |
| `sysone classify|check|score|rank --input file.json` | CLI mirrors of the tools (skill falls back to CLI where MCP isn't registered) |
| `sysone bench [--suite coding-v0] [--ab]` | Latency/accuracy/calibration/memory; `--ab` = token-savings A/B |
| `sysone calibrate --data labeled.jsonl` | Fit temperature/thresholds (Phase 4) |
| `sysone upgrade` | Upgrade shim → runtime → manifest; keep pins unless `--latest-manifest` |
| `sysone uninstall [--purge-models]` | Reverse integrations from the install manifest; stop daemon; optional purge |

Exit codes: 0 ok · 1 runtime/API failure · 2 usage/config problem · 3 partial success (some agents failed). Output: human text by default, `--json` for machines.

### 9.1 First-run wizard — backend choice (the core user journey)

**Journey:** user runs one command in any terminal (macOS Terminal/iTerm, Linux shell, Windows PowerShell/Windows Terminal, VS Code integrated terminal) → `sysone init` → hardware check → **choose how decisions are made** → everything is installed and every detected agent is wired up → user restarts the agent(s) and uses it. No other manual steps.

**Step 1 — Hardware check (always, ~2 s).** Print a one-line summary (chip/CPU, RAM, GPU/VRAM, OS) and the profile it implies (§5.2).

**Step 2 — Choice screen** (interactive; skipped by `--backend …` / `--yes`):

```
How should sysone make decisions on this machine?   (Apple M4 · 16 GB · macOS)

  [1] Hosted — I have an API key                     most accurate · text leaves this machine
        a) TypeSafe Jev (your Jev key)
        b) OpenRouter   (your OpenRouter key; Jev or hosted Kev models)
        c) Other /v1/systemone URL (team server, Telnyx, Opper, LLM Gateway, …)
  [2] Local — free, private, offline                 recommended for this machine: ★ Laya (MLX), 843 MB
        ★ recommended   · smaller/faster alt · larger/more accurate alt (if hardware allows)
  [3] Tier-0 only — no model                         rule-based answers (test runner, lint, build commands)
  [4] Both — local first, hosted fallback            local answers when confident, hosted only on `review`
```

- **Recommendation logic:** local options are listed from the profile table (§5.2) and bake-off ADR (§12.4): the *smallest model meeting the accuracy bar* is starred, with one smaller and one larger alternative **only if the hardware can run them** (e.g., small CUDA GPU → Kev-0.8B; Apple Silicon → Laya via MLX/CoreML; CPU-only laptop → Laya ONNX INT8; big GPU → Kev-4B/9B). Show size, expected latency (from the hardware-report matrix, or "unmeasured") and an **honest accuracy note** (small models are weaker out-of-domain; hosted Jev scores higher in independent comparisons ⚠️).
- **Hosted keys:**
  - *TypeSafe Jev:* key via env var `TYPESAFE_API_KEY` (base URL `https://api.typesafe.ai`, model `jev-latest`) ✅ (convention used by the official SDKs and `jev-code`).
  - *OpenRouter:* `OPENROUTER_API_KEY`; same System One request shape, model field selects the model (⚠️ one source says Kev-4B is hosted there as `jaredpalmer/kev-4b`, while 0.8B/9B are not — verify live in Phase 0; this gives GPU-less users a hosted *open* model option).
  - *Custom URL:* base URL + optional bearer token; works with any compatible server.
  - The wizard validates the key with one live canary request (cost ≈ 0) and reports latency before continuing.
- **Key storage (ADR-006):** keys live **only in sysone's own config**, in the OS keychain via `keyring` (macOS Keychain / Windows Credential Manager / Secret Service), with a 0600 file fallback or an `--api-key-env VAR` reference that stores *no secret at all*. **Keys are never copied into agents' config files** — the shim talks to the daemon, and only the daemon holds the key. (This is deliberately different from `jev-code`, which copies the key into each harness config because some harnesses filter the environment; our shim/daemon split avoids that leak surface.) `doctor` shows a masked hint only; logs never contain keys or request bodies.
- **Privacy disclosure (hosted/hybrid):** before first use print exactly what is sent (the `state` text and questions the agent passes — i.e., log excerpts/code snippets), to whom, and that local mode sends nothing. Offer secret-scrubbing (default on for hosted), and label every envelope `backend.remote:true`.
- **Local choice triggers provisioning:** create runtime venv → install profile deps → download pinned model → warm-up → canary → show measured latency. Show total download size up front; require consent above 500 MB (`--yes` skips).
- **Hybrid (option 4):** local backend answers first; if `decision:"review"` and a hosted key exists, retry once on hosted. Off by default; never sends data remotely without the user having chosen option 1 or 4.
- **Changing the choice later:** `sysone backend set …` / `sysone init --reconfigure`; no agent re-registration needed (agents only know the shim).
- **Non-interactive/CI:** `sysone init --yes --backend local` or `--backend hosted:openrouter --api-key-env OPENROUTER_API_KEY`; fails fast with exit code 2 if a required choice is missing.

**Step 3 — Integrate every agent found** (§8): register MCP (CLI-first), install the skill globally, optionally auto-approve the read-only tools and add the activation nudge (each asked once, default shown).

**Step 4 — Finish:** live end-to-end check, summary table (below), and a "**restart these agents**" list (Cursor, Antigravity, OpenCode, Cline load MCP only at startup).

**What "agents use it actively" really means:** after setup the tools and skill are present in every repo, but *whether the agent calls them is the agent's own decision*, driven by the skill `description`. Mitigations, in order of strength: strong trigger phrasing → opt-in global instruction nudge → Claude Code hooks → measuring activation rate in agent E2E tests (§12.1). It is improved by design, not guaranteed; the README must say so.

**Target `init` output (illustrative — numbers filled from real detection, never hardcoded):**
```
╭──────────────── sysone ────────────────╮
│ Hardware   Apple M4 · 16 GB unified     │
│ Profile    apple  (MLX)                 │
│ Model      laya-en @ 3f9a1c2 · 843 MB   │
│ Download   843 MB → ~/Library/Caches/…  │
├─ Agents ────────────────────────────────┤
│ Claude Code  ✓ registered (user scope)  │
│ Codex        ✓ registered               │
│ Cursor       ✓ registered · restart     │
│ OpenCode     ✓ registered · restart     │
│ Antigravity  ! config patched · verify  │
├─ Skill ─────────────────────────────────┤
│ ~/.claude/skills/sysone  ~/.agents/…    │
╰─ Live check: classify p50 14 ms ────────╯
```

---

## 10. Security, privacy & supply chain

| Area | Control |
|---|---|
| Local-only default | No code/log content leaves the machine in local mode; remote backend is explicit, labeled in every envelope (`backend.remote:true`), with optional secret-scrubbing (regexes for keys/tokens/`.env` lines) |
| API keys (hosted backends) | OS keychain via `keyring` (or env-var reference, no secret stored); held only by the daemon; **never written into agent configs**, logs, envelopes, or `doctor --report`; masked in all output (ADR-006) |
| IPC | UDS 0600 / loopback + token; no unauthenticated TCP; refuse non-loopback bind without `--serve-team` + TLS/token |
| Config tampering | §8.2 rules; install manifest; hash of inserted values |
| Model integrity | Pinned commit SHA + per-file SHA-256; no `trust_remote_code`; safetensors / `weights_only`; third-party conversions re-validated for parity |
| Python supply chain | Trusted Publishing (OIDC) + PEP 740 attestations; `uv.lock` + shipped constraints; Dependabot; `pip-audit` in CI; CycloneDX SBOM attached to releases; minimal base deps |
| Installer scripts | `curl | sh` / PowerShell bootstrappers are short, versioned, hash-published, and only install `uv` + `uv tool install sysone`; never run unreviewed remote code |
| Telemetry | None. If ever added: opt-in, anonymous, documented, off in CI |
| Classifier abuse | §7.3; fail-closed |
| Vulnerability reporting | `SECURITY.md` + GitHub private vulnerability reporting |
| Licenses | Manifest `license` field; CI blocks non-allow-listed licenses; datasets' licenses tracked for eval/fine-tune data |

---

## 11. Failure modes & degradation matrix

| Condition | Behavior |
|---|---|
| Models not downloaded | Tools return `review` + `reason:"no_model"` + hint (`sysone models pull`); Tier 0 still works |
| Daemon cold/warming | Wait ≤ 5 s then `review` + `reason:"warming"`; warm in background |
| Daemon crash | Shim restarts once; else `review` |
| GPU OOM | Daemon drops caches & retries (Kev ships OOM-retry ✅); else fall back to smaller model/CPU profile; log |
| Input too large | Strategy §4.6 → `truncated:true` → `review` |
| Agent config changed/removed | `doctor` flags drift; `sysone agents add` repairs |
| Runtime/shim version skew | Shim refuses heavy ops, instructs `sysone upgrade` |
| Offline | Cache-only; clear message |
| Unsupported platform | P0 + optional remote |

---

## 12. Quality: testing, benchmarks, evals

### 12.1 Test pyramid
1. **Unit:** hardware parsers against real-output fixtures; profile selector (table-driven); manifest schema; decision policy; truncation strategies; config patchers with **golden files** (JSON, JSONC-with-comments, TOML-with-comments, empty, malformed, CRLF, BOM, 0600 perms); idempotency & uninstall round-trip property tests.
2. **Contract:** MCP server tested with the SDK's **in-memory `Client`** (v2) against the `mock` backend; JSON-schema validation of every tool envelope; stdout-purity test (nothing but protocol on stdout).
3. **Integration:** daemon lifecycle (start/idle-stop/crash-restart/lock contention), IPC auth, micro-batching, backend parity tests (argmax agreement vs reference on a fixed suite).
4. **CI matrix:** `ubuntu-latest`, `ubuntu-24.04-arm`, `macos-latest` (arm64), `windows-latest`; shim on Python 3.10–3.13; runtime venv 3.12/3.13. GPU/Apple-ANE jobs are manual/self-hosted and tracked via **hardware-report issues**.
5. **Agent E2E (nightly/manual, sandboxed `HOME`):** headless runs — e.g., Claude Code non-interactive mode and `codex exec` — asking a question that must trigger a tool; assert the tool appears in the transcript. ❓ confirm headless flags per agent in Phase 0.

### 12.2 Coding-decision eval set (`evals/coding-v0`) — **your real moat**
The base models were trained on banking77/AG-News/BoolQ-style data (✅ Kev training sources); coding decisions are out-of-distribution. Build a held-out, license-clean benchmark (target 300–500 labeled items to start):
1. CI/test-failure root-cause (infra-flake / real bug / env / timeout / dependency)
2. Error-class (syntax / type / runtime / network / permission / resource)
3. File relevance ranking (issue text + file list → relevant set)
4. Command risk (safe / needs-review / destructive) — **asymmetric cost metric**
5. Diff-vs-description consistency (yes/no/uncertain)
6. Commit/PR classification (type, semver impact)
7. Test/lint/typecheck command selection (validates Tier 0)
Sources: public repos' CI logs and issues with permissive licenses; document provenance; prevent train/test leakage (the Kev authors' "locked test read once" discipline ✅ is a good template).

### 12.3 Metrics (all reported by `sysone bench`)
Accuracy · **coverage@≤5 % error** (share automatable) · ECE · Brier · **confident-error rate (p ≥ 0.9 & wrong)** · escalation rate · latency p50/p95 (cold/warm) · peak RSS/VRAM · **end-to-end A/B**: same agent tasks with vs without `sysone` → tokens, wall-clock, task success. **A release that cannot show a net saving on at least one task family must say so in its README.**

### 12.4 Bake-off (Phase 2→4)
Run candidates {Laya EN/multilingual (ONNX/MLX/CoreML), Von, jeff, Kev-0.8B/4B/8B/9B, CLM-8B (with a candidate generator), edgejev INT8} on `coding-v0` across reference machines (M-series Mac, x86 laptop CPU, RTX 4060, A100/H100). Output a decision table that **replaces §5.2 defaults** and is committed as an ADR.

### 12.5 Specialization path (Phase 5)
Kev ships LoRA training (`kev.train`, ~20 min on one H100 for the 0.8B recipe ✅; one epoch on 5,219 complaints lifted Kev-4B 0.804 → 0.904 ⚠️). Laya is explicitly "a base to specialise". Fine-tune a `*-code` head on a **licensed, public** coding-decision dataset, publish weights + model card + eval under your HF org, add to manifest. This is the most defensible long-term asset.

---

## 13. Packaging & release engineering

### 13.1 Repository layout
```
sysone/
├─ pyproject.toml                # hatchling; src layout
├─ README.md                     # contains `mcp-name: io.github.<owner>/<name>` (HTML comment OK)
├─ server.json                   # MCP Registry manifest
├─ LICENSE  NOTICE  SECURITY.md  CONTRIBUTING.md  CODE_OF_CONDUCT.md  CHANGELOG.md
├─ AGENTS.md  CLAUDE.md          # conventions for contributors' coding agents
├─ uv.lock  constraints/{cpu,apple,cuda12,cuda13,dml,openvino}.txt
├─ src/sysone/
│  ├─ _brand.py                  # single source of the project name
│  ├─ cli/ (typer app, commands/*)
│  ├─ hardware/ (detect.py, probes/{darwin,linux,windows,nvidia,amd,intel}.py, profile.py, report.py)
│  ├─ registry/ (manifest.yaml, schema.json, download.py, verify.py)
│  ├─ runtime/ (env.py, daemon.py, ipc.py, lifecycle.py, logging.py)
│  ├─ backends/ (base.py, mock.py, remote_systemone.py, kev_serve.py, laya_onnx.py, laya_mlx.py, laya_coreml.py, clm_vllm.py)
│  ├─ decisions/ (envelope.py, policy.py, calibrate.py, truncate.py, tier0/project_facts.py)
│  ├─ mcp/ (server.py, tools.py)
│  ├─ integrations/ (base.py, backup.py, jsonc.py, toml_edit.py, claude_code.py, codex.py, cursor.py, windsurf.py, opencode.py, antigravity.py, vscode.py, cline.py, roo_family.py, generic_skill.py)
│  └─ skills/sysone/ (SKILL.md, references/*.md)
├─ tests/ (unit/ contract/ integration/ e2e/ fixtures/)
├─ evals/coding-v0/              # data, labels, provenance, scripts
├─ docs/ (adr/, spikes/, benchmarks/, integrations/<agent>.md, models/<family>.md, contributing/{add-an-agent,add-a-model}.md)
├─ scripts/ (install.sh, install.ps1)
└─ .github/ (workflows/{ci,release,codeql,scorecard}.yml, ISSUE_TEMPLATE/*, PULL_REQUEST_TEMPLATE.md, CODEOWNERS, dependabot.yml)
```

### 13.2 `pyproject.toml` sketch (verify every pin at implementation time)
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "sysone"                         # PLACEHOLDER — rename gate §1.4
dynamic = ["version"]
description = "Local System One decision layer for coding agents"
readme = "README.md"
license = "Apache-2.0"
requires-python = ">=3.10"              # shim only; runtime venv is uv-managed 3.12/3.13
dependencies = [
  "mcp>=2,<3",
  "typer>=0.12", "rich>=13", "httpx>=0.27", "pydantic>=2",
  "platformdirs>=4", "psutil>=5.9", "tomlkit>=0.13", "filelock>=3.13",
  "huggingface_hub>=0.34",
]
[project.optional-dependencies]            # installed ONLY into the managed runtime venv
runtime-onnx-cpu    = ["onnxruntime>=1.2"]
runtime-onnx-cuda   = ["onnxruntime-gpu"]
runtime-onnx-dml    = ["onnxruntime-directml"]
runtime-onnx-ov     = ["onnxruntime-openvino"]
runtime-mlx         = ["mlx"]
runtime-torch       = ["torch", "transformers>=5.17", "peft>=0.21"]   # Kev constraint ✅
[project.scripts]
sysone = "sysone.cli:app"
# NOTE: no direct-URL (git) dependencies — PyPI rejects them. Kev is provisioned at init time.
[tool.uv]
conflicts = [[{extra="runtime-onnx-cpu"},{extra="runtime-onnx-cuda"},{extra="runtime-onnx-dml"},{extra="runtime-onnx-ov"}]]
```

### 13.3 Distribution channels
1. **PyPI** (primary): `uv tool install sysone` · `pipx install sysone` · `pip install sysone` · zero-install trial `uvx sysone init` (init self-persists, §5.3).
2. **Bootstrap one-liners** (Phase 3): `install.sh` / `install.ps1` → install `uv` (if absent) → `uv tool install` → `sysone init`.
3. **MCP Registry** (after PyPI release): `server.json` via `mcp-publisher` in CI with `github-oidc`.
4. **Skills ecosystem:** `npx skills add <owner>/<repo> --skill sysone`; Claude Code plugin marketplace; awesome-mcp / awesome-jev lists.
5. Later: Homebrew tap, winget, npm wrapper (`npx`) for Node-first users.

### 13.4 Release pipeline (`release.yml`, on tag `vX.Y.Z`)
1. Lint/type/test matrix must be green. 2. `uv build` (sdist+wheel). 3. Publish to **TestPyPI** (first releases) then **PyPI** via **Trusted Publishing** (OIDC; protected `pypi` environment requiring owner approval) with attestations. 4. Verify README on PyPI contains the `mcp-name:` marker **in the released artifact**. 5. `mcp-publisher validate` **before** login (description ≤ 100 chars; versions in `pyproject`/`server.json`/README agree — enforced by a unit test) → `login github-oidc` → `publish`. 6. GitHub Release with changelog, SBOM, checksums. 7. Post-release smoke: clean VM matrix runs `uvx sysone doctor`.

`server.json` starting point (❓ generate with `mcp-publisher init` and validate — do not trust this verbatim):
```json
{
  "$schema": "https://registry.modelcontextprotocol.io/schemas/server.json",
  "name": "io.github.<owner>/sysone",
  "description": "Local System One decision models for coding agents: fast, calibrated typed decisions.",
  "version": "0.1.0",
  "packages": [{ "registryType": "pypi", "identifier": "sysone", "version": "0.1.0",
                 "runtimeHint": "uvx", "transport": { "type": "stdio" } }]
}
```

---

## 14. Open-source project setup (for contributions)

- **License:** Apache-2.0 (patent grant; matches Kev/Laya/CLM/Qwen). Add `NOTICE`; list third-party model licenses in `docs/models/`. Use **DCO** sign-off (lighter than a CLA).
- **Governance files:** `CODE_OF_CONDUCT.md` (Contributor Covenant), `CONTRIBUTING.md`, `SECURITY.md`, `CODEOWNERS`, `CHANGELOG.md` (Keep a Changelog), SemVer, ADRs.
- **Issue forms:** Bug · **New agent integration** · **New model** · **Hardware compatibility report** (paste `sysone doctor --report` → crowdsourced compatibility matrix in `docs/hardware.md`) · Feature request.
- **Contribution magnets:** `docs/contributing/add-an-agent.md` (implement `Integrator`, add golden-file tests, add a docs page — checklist) and `add-a-model.md` (manifest entry + parity test + license check). Label `good first issue` for new agent configs and hardware fixtures.
- **Repo automation:** pre-commit (ruff, ruff-format, pyright/mypy), Dependabot, CodeQL, OpenSSF Scorecard, branch protection, required checks, release-please or manual SemVer, GitHub Discussions on.
- **Contributor-agent friendliness:** root `AGENTS.md`/`CLAUDE.md` stating: run `uv run pytest`, never touch real HOME, ADR rules, "no stdout in MCP code", evidence-legend convention.
- **README must contain:** 30-second install, `init` demo GIF, support matrix (agents × OS × hardware with ✅/⚠️ and last-verified dates), honest benchmark table with machine specs, privacy statement, "how it decides" (tiers + abstention), uninstall, comparison with prior art (credit them), trademark/non-affiliation disclaimer, `mcp-name:` marker.
- **Credit & interoperability:** link TypeSafe docs, Kev, Laya, CLM, laya-mlx/coreml, edgejev, and existing Jev MCP projects; open issues upstream for bugs found (e.g., Kev/Laya packaging).

---

## 15. Roadmap — agent-executable phases

> Each task: **DoD** = Definition of Done. Record results in `docs/spikes/` or `docs/benchmarks/`. 🛑 = human gate.

### Phase 0 — Spikes & decisions (2–3 days)
| Task | DoD |
|---|---|
| **S1 Name** — check 8–10 candidates on PyPI/GitHub/npm/MCP-Registry namespace; 🛑 owner picks | `_brand.py` + `pyproject` use the chosen name; `agent-s1` ruled out in an ADR |
| **S2 Kev spike** — pinned SHA; provision via tarball; run `kev.serve` for 0.8B and 4B on (a) CUDA box, (b) Apple Silicon, (c) CPU; verify Python 3.12/3.13 constraint, `fla` behavior, `head.pt` `weights_only` load; measure cold/warm latency, RSS/VRAM | `docs/spikes/kev.md` with a table; go/no-go per profile |
| **S3 Laya spike** — ONNX (CPU, DirectML if available), laya-mlx, laya-coreml; **argmax parity** vs PyTorch on a 60+ item suite; INT8 vs FP32 latency; TF-hang workaround | `docs/spikes/laya.md`; parity ≥ 99 % argmax or documented deviation |
| **S4 MCP v2 skeleton** — minimal `MCPServer` (confirm v2 import path), stdio, one echo tool, in-memory `Client` test; **register in Claude Code via `claude mcp add --scope user`** and call it | Transcript shows tool call succeeded; startup < 500 ms |
| **S5 Config-path verification** — on real installs, confirm for each row of §8.3: path, schema, restart need, skill dir, headless smoke command | `docs/integrations/<agent>.md` per agent with evidence + versions; resolve every ❓ in §2.2/§8.3 |
| **S6 Antigravity** specifically: shared vs CLI-specific `mcp_config.json`; skill dir actually honored | Documented decision + fallback |
| **S7 Von / OpenDecider / jeff licenses & quick eval** | Allow-list decision (🛑 for non-OSI) |
| **S8 Prior-art review** — read `jev-code`, `jev-mcp` (local-Kev one), `edgejev`, `laya-mlx` source; list what to reuse (license permitting), interoperate with, or upstream | `docs/prior-art.md` |

### Phase 1 — MVP "it installs and a tool call works everywhere" (1–2 weeks)
- Repo scaffold (§13.1), CI (lint/type/test, matrix), `AGENTS.md`, ADRs 0001–0005.
- `hardware/` detection + fixtures; profile selector (table-driven).
- Shim + daemon with **`mock`** and **`remote_systemone`** backends (so `kev.serve` or hosted Jev works on day one); envelope/policy/truncation; **Tier-0 `project_facts`** (Python, Node/TS, Rust, Go, Java/Gradle/Maven, .NET, Ruby, PHP; monorepos: pnpm/yarn/npm workspaces, Nx, Turborepo, Cargo workspaces, uv/poetry).
- Integrators: Claude Code, Codex, Cursor, OpenCode, Antigravity; backup/atomic/idempotent/uninstall; JSONC + TOML editors.
- Skill v1 + `~/.agents/skills` install; `init` **with the first-run backend wizard (§9.1: hosted key / local / Tier-0; keychain key storage; live key validation)**, `doctor`, `uninstall`. In Phase 1 the "local" option may point at a user-run `kev.serve`; managed local provisioning lands in Phase 2.
- **DoD:** on clean macOS, Linux and Windows VMs: `uv tool install` → `sysone init --yes --remote-url <mock/Kev>` → in **each of the five agents** a prompt triggers `project_facts`/`classify` successfully; `sysone uninstall` restores all touched files **byte-for-byte**; all unit/contract tests green; TestPyPI release 🛑.

### Phase 2 — Local models & hardware profiles
- `registry/` manifest + downloader (resumable, hash-verified, consent). Managed runtime venv + constraints per profile; ephemeral-run guard.
- Backends: `laya_onnx` (CPU/DML/CUDA), `laya_mlx`/`laya_coreml`, `kev_serve` (CUDA first; Apple via supported path).
- Daemon lifecycle (lock, idle stop, warm, logs), micro-batching, calibration plumbing.
- `bench` v1 + `evals/coding-v0` v0 (≥ 150 items); first bake-off numbers.
- **DoD:** P1, P2, P4 profiles auto-selected and working on reference machines; documented p50/p95 latencies; `doctor --live` green; OOM/failure fallbacks tested.

### Phase 3 — Reach & polish
- Integrators: VS Code (Copilot), Cline (all host editors), Windsurf, Roo-family (legacy), Gemini CLI (legacy), WSL/remote; `--project` scope; `--nudge`; optional Claude Code hooks; bootstrap installers; Claude Code plugin marketplace; MCP Registry publication 🛑; docs site; hardware-report issue flow.
- **DoD:** support matrix in README with last-verified dates; registry listing live; ≥ 3 external contributors can add an agent following the guide (dry-run with a volunteer or a fresh agent session).

### Phase 4 — Evidence-driven defaults & server tier
- Complete bake-off → ADR replaces §5.2 defaults; per-task calibration & thresholds; `sysone calibrate`; CLM-8B/vLLM server tier + candidate generator; Kev-4B/9B tiers; **team shared daemon** (`--serve-team`, token/TLS); **A/B token-savings study** published honestly.
- **DoD:** README benchmark table reproducible with one command; defaults justified by data.

### Phase 5 — Specialization & community
- Public coding-decision dataset (licensed), fine-tuned `*-code` heads (Kev LoRA / Laya head), HF model cards, manifest entries, blog/paper; Pi extension; npm wrapper; Homebrew/winget.

---

## 16. Risks & mitigations

| # | Risk | Likelihood / Impact | Mitigation |
|---|---|---|---|
| R1 | Tiny models are weak out-of-domain (✅ Kev-0.8B OOD 0.65; Laya zero-shot ≈ random) | High / High | Tier 0 first; abstention thresholds; bake-off; `coding-v0`; fine-tuned heads; default to `review` |
| R2 | Token savings don't materialize | Med / High | Measure A/B; focus on bulk-triage/ranking; say so publicly if marginal |
| R3 | Ecosystem churn (weeks-old models, Python/torch pins moving, Kev code changing) | High / Med | Manifest + SHA pins; adapter isolation; nightly "pins still install" CI job |
| R4 | Agent config formats change / agents die (Roo ✅ already did; Gemini CLI deprecated) | High / Med | CLI-first integrators; `doctor` drift detection; tiered support labels; community-owned integrators |
| R5 | Prior art/competition (many Jev wrappers) | High / Med | Differentiators §1.5; interoperate; contribute upstream |
| R6 | Name/trademark conflict (Agent S; Jev/TypeSafe) | Certain / Med | Rename gate; disclaimer; no "Jev" in names |
| R7 | Heavy installs (torch GBs), Windows/ARM wheel gaps, Intel-Mac gaps | Med / Med | ONNX/MLX defaults; torch only for CUDA tier; P0/remote fallback; per-platform verification |
| R8 | Config corruption of other tools | Low / **Severe** | §8.2 rules; golden-file tests; CLI-first; backups; never "repair" |
| R9 | MCP v2 client lag / stateless-spec implications | Med / Med | Server serves both eras ✅; no server→client calls; contract tests with both |
| R10 | Third-party model conversions (ONNX/MLX/CoreML) have bugs or licenses | Med / Med | Parity gate; pin SHAs; license allow-list; prefer own conversions after S3 |
| R11 | Classifier manipulated by adversarial repo text | Med / Med | Advisory-only; asymmetric thresholds; skill prohibitions |
| R12 | Agents ignore the skill | Med / Med | Strong `description`; opt-in nudge; hooks; measure activation rate in E2E |

---

## 17. Open questions for the owner (🛑 answer before/at Phase 0)

1. Final **project name** (§1.4) and GitHub owner/org for `io.github.<owner>/…`.
2. Allow **hosted fallback** (e.g., via OpenRouter) as an opt-in backend? (Recommended: yes, clearly labeled.)
3. Depend on **Kev via pinned git/tarball** at init time (recommended for Phase 2) vs vendor a minimal loader?
4. Support stance for **legacy agents** (Roo, Gemini CLI): best-effort/labeled (recommended) vs exclude.
5. **Telemetry:** none (recommended) vs opt-in anonymous.
6. Team-server mode in scope for v1.x?
7. Who funds/hosts GPU CI and hardware verification (community reports vs self-hosted runner)?

---

## Appendix A — Config snippets (illustrative; the integrator must follow the real spikes)

**Claude Code (preferred, CLI):**
```bash
claude mcp add --scope user sysone -- /ABS/PATH/sysone mcp     # flags BEFORE the `--`
claude mcp get sysone
```
Fallback `~/.claude.json`: `"mcpServers": {"sysone": {"type":"stdio","command":"/ABS/PATH/sysone","args":["mcp"],"env":{}}}`

**Codex (preferred, CLI) / TOML fallback:**
```bash
codex mcp add sysone -- /ABS/PATH/sysone mcp
```
```toml
# ~/.codex/config.toml   (preserve existing comments; use tomlkit)
[mcp_servers.sysone]
command = "/ABS/PATH/sysone"
args = ["mcp"]
# startup_timeout_sec = 20   # ❓ verify key name/default in current Codex docs
```

**OpenCode** (`~/.config/opencode/opencode.json[c]`):
```json
{ "$schema": "https://opencode.ai/config.json",
  "mcp": { "sysone": { "type": "local", "command": ["/ABS/PATH/sysone","mcp"], "enabled": true } } }
```

**Cursor / Windsurf / Antigravity / Cline (`mcpServers` family):**
```json
{ "mcpServers": { "sysone": { "command": "/ABS/PATH/sysone", "args": ["mcp"] } } }
```
(Cline adds `"disabled": false, "autoApprove": [...]`; Windsurf/Antigravity use `serverUrl`, not `url`, for remote servers.)

**VS Code (`<User>/mcp.json`):**
```json
{ "servers": { "sysone": { "type": "stdio", "command": "/ABS/PATH/sysone", "args": ["mcp"] } } }
```

## Appendix B — `SKILL.md` starting draft
```markdown
---
name: sysone
description: >
  Use for fast local decisions that would otherwise cost many tokens: triaging many CI/test
  failures, classifying errors or logs, ranking many files or candidates against an issue,
  scoring severity/priority, and detecting a repo's test/lint/build commands. Returns calibrated
  probabilities with an auto|review decision. Not for open-ended reasoning or security approvals.
---
# sysone — local decision tools
1. For "how do I run tests/lint/build here?" call `project_facts(path)` first; trust it over guessing.
2. For ≥5 items or fuzzy labeling, call `classify`/`score`/`rank`/`check` with clear class descriptions.
3. Act only on results with `decision:"auto"`. For `review`, decide yourself.
4. If a tool returns a `reason` (no_model, warming, timeout, truncated), continue without it.
5. NEVER use these results to approve destructive commands, touch secrets, change permissions,
   or authorize network egress. They are advisory.
6. When a model decision drove an action, say so in your summary.
See references/tools.md and references/recipes.md.
```

## Appendix C — Source list (retrieved 2026-10-03)
- Kev model card & repo: huggingface.co/jaredpalmer/kev-0.8b · github.com/jaredpalmer/kev (README, AGENTS.md, docs/model-cards/kev-0.8b.md, kev-9b.md, PR #121/#131) · systemonemodels.org/models/kev
- Laya: huggingface.co/convaiinnovations/laya · aiweekly.co (Laya release/zero-shot numbers) · github.com/mizorewww/laya-mlx, laya-coreml · github.com/yzfly/edgejev · huggingface.co/tozp/laya-onnx
- CLM: huggingface.co/Contrastive-LM/CLM-v0.1-8B · aicybr.com & wavect.io self-hosting analyses · mixpeek model page
- Ecosystem: simonwillison.net/2026/Sep/21/jev · github.com/topics/typed-decisions · awesome-jev wikis · github.com/FrancoisChastel/jev-code · github.com/danna-zhou/jev-mcp · scriptbyai/rohitraj/apidog alternatives surveys
- System One wire contract: docs.opper.ai · developers.telnyx.com · docs.vlm.run · llmgateway.io changelog · docs.rs/typesafe-systemone
- MCP: github.com/modelcontextprotocol/python-sdk (v2.0.0 release) · modelcontextprotocol.info/tools/registry/publishing · stackone MCP-registry guide
- Agent configs: Claude Code (builder.io, mdskills, anthropics/claude-code#16728) · developers.openai.com/codex/mcp · learn.microsoft.com Antigravity page · medium.com/google-cloud Antigravity config article · github/github-mcp-server#2529 · dev.to MCP config comparison · docs.stacklok.com client-compatibility · ionos/crawlbase OpenCode docs · github.com/anomalyco/opencode PR #5757
- Skills: github.com/vercel-labs/skills (skills CLI path table) · opencode.school/lessons/skills
- Roo Code shutdown: fast.io, amplifying.ai, rywalker.com, aicoolies.com
- ONNX Runtime EPs: onnxruntime.ai/docs/execution-providers · darktable GPU doc · npu-easy
- Agent S naming: verdent.ai Agent S guide (simular-ai/Agent-S)

*End of document.*
