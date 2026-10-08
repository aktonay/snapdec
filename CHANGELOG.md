# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.6.0] — 2026-10-08

### Added
- imajev family (`mohit67890/imajev`, Apache-2.0) as fourth managed local
  backend `imajev` (port 8904): imajev-2B / 4B / 9B on Qwen3.5 bases, each
  pinned to a verified commit SHA. snapdec runs upstream's own pinned
  server (`scripts/playground/server.py`, `--rotations 1`) — no shim
  authored (ADR-0011, contrast ADR-0010). Flat `/v1/models` body and the
  no-`/health` wire are handled snapdec-side; 422/500 errors already
  convert to fail-closed review envelopes (NFR-4 unchanged).
- Dual download per model: pinned base snapshot via their
  `download_model.py` (absolute `HF_HOME` under SNAPDEC_HOME) plus pinned
  adapter snapshot into a stable path so daemon restarts never re-download.
- **Live download progress** (owner request 2026-10-07): model-base,
  adapter, and pip installs run with stderr inherited — tqdm byte and
  speed bars render live during multi-GB downloads instead of a silent
  captured console that looks hung on slow links.
- Hardware-gated catalog entries citing the JevBench board (2026-09),
  kept as a third stat scale never blended with kev breadth-v1 or the
  vllm-sr card (ADR-0008 rule). RAM floors 12/24/48 GB x86 (FP32 CPU),
  8/16/32 GB Apple (real MLX fast path via `--backend mlx`); no star —
  unbenched in snapdec until a bench doc lands.
- Wizard + `init --backend local --model imajev-…` inference for all
  three variants (`mohit67890/` org fixup, lowercase).

### Fixed
- Placeholder-bundle trap: their repo tarball ships
  `artifacts/model.json` as a placeholder that a plain `.exists()` gate
  accepted, skipping the ~4.6 GB base download and crashing the server
  at load (`ValueError: Local model snapshot is missing`). Bundles are
  now json-parsed: empty/relative-placeholder/missing-snapshot paths are
  rejected before launch, and the base download is verified again after
  it runs (ADR-0011 §3).
- Resurrect window: `ensure_running` waited a flat 120 s, so a daemon
  restart declared the imajev FP32 cold load (minutes) dead while it was
  still loading. Now kind-aware — 600 s for kev/decision2/imajev, 120 s
  for laya — with a 10 s heartbeat on stderr and a log-path note on
  failure (ADR-0011).
- Pid-reuse guard on Windows: a stale daemon state file could point at
  an unrelated process that inherited the PID; `stop_daemon` now
  terminates only a pid whose process name looks like python/snapdec
  (`lifecycle._pid_alive` name check, ADR-0011).
- `(paid)` label wrongly appended to local-managed models in init
  output — now only shown for hosted routers.

## [0.5.1] — 2026-10-07

### Changed
- Decision 2.0 family is now selectable on Apple Silicon via the plain
  torch CPU path (was `runs_on_apple=False` in 0.5.0). Unified-memory
  floors: Kai/Eos 8 GB, Sol/Nox 32 GB. No MLX build exists for the
  family, so the new `mlx_on_apple` catalog flag stays False on d2 and
  the wizard keeps showing `[slow on CPU]` on Apple — Kev 0.8B (MLX)
  remains the recommended fast local pick there. Apple latency strings
  say "bench pending" until a Mac `snapdec bench` lands (ADR-0010 §4
  amendment). MPS backend still unvalidated.

## [0.5.0] — 2026-10-06

### Added
- Decision 2.0 family (`vllm-sr`, Apache-2.0) as third managed local
  backend `decision2` (port 8903): Kai-0.6B / Eos-0.8B / Sol-2B / Nox-4B,
  each pinned to a verified commit SHA. Answer wire format matches §4.5
  exactly, so the daemon protocol is unchanged (ADR-0010).
- `runtime/d2serve.py`: stdlib 127.0.0.1-only serve shim (two-phase
  trust_remote_code load: pinned snapshot, then `HF_HUB_OFFLINE=1`
  before transformers import; fail-closed error envelopes; 2-lane
  semaphore around `system_one`).
- Hardware-gated catalog entries with card stats labeled by source —
  `vllm-sr card 2026-10` index kept separate from kev's breadth-v1
  held-out numbers (ADR-0008 rule). Eos-0.8B starred on cpu/windows-gpu
  profiles. Lux-9B/Vega-27B omitted (cards unfetched).
- Wizard + `init --backend local --model vllm-sr/…` inference for all
  four variants (case-sensitive repo ids).

### Fixed
- Request-timeout bug: `RemoteSystemOne` hardcoded 5 s and `ipc._client`
  10 s, so the 8-way CLI fan-out against a CPU-served model exceeded the
  limit and produced silent failure envelopes. New
  `Config.request_timeout_s` + `effective_request_timeout()`: explicit
  override wins; 60 s local-managed/local-server; 5 s hosted. Threaded
  through `daemon.build_backend`, `ipc._client`, `_canary` (ADR-0010 §6).

## [0.4.2] — 2026-10-04

### Added
- Official banner showcase artwork embedded in documentation and package distribution.
- Enhanced PyPI project metadata with direct links to repository, documentation, issues, and changelog.

## [0.4.1] — 2026-10-04

### Changed
- Shared `add_status` helper across MCP server and CLI commands so both
  consistently output the status footer line.
- Comprehensive overhaul of `README.md`: visual badges, architecture flow,
  full agent integration guides, and search optimization.

## [0.4.0] — 2026-10-04

### Added
- `snapdec update`: checks PyPI and upgrades the installation (uv tool →
  pip → pipx). `init` and `doctor` print a one-line update notice
  automatically (cached 24 h; a public-metadata read, no user data —
  ADR-0009). Act is always explicit; nothing auto-installs silently.
- Status footer on every Tier-1 answer: `· snapdec 0.4.0 · model · ms ·
  auto/total · ~N tok offloaded` — visible in the agent transcript after
  each tool call, quiet single field, informational only.
- The MCP shim already lazy-starts the daemon on first tool call and
  resurrects a dead managed backend (unchanged, now documented).

## [0.3.1] — 2026-10-04

### Fixed
- Daemon could be unreachable on macOS: when the UDS socket path exceeded
  the 104-byte `sun_path` limit the daemon fell back to loopback TCP, but
  the state file still advertised the (never-bound) UDS path — clients
  pinged a socket that didn't exist. State now records the actual
  transport.
- TCP bind skipped `socket.getfqdn` — reverse DNS could hang for minutes
  on hosts whose resolver never answers, stalling the daemon before it
  served a single request.
- CI matrix green on all 3 OS × 3 Pythons (first fully green run).

## [0.3.0] — 2026-10-04

### Added
- Kev 1.0 support: kev-9b (DI 41.0) and kev-27b (DI 52.3, near-Jev) join
  the hardware-gated catalog; pin bumped to the 1.0 tree and install now
  uses `kev[serve]` (carries fastapi/uvicorn/typesafe-sdk, MLX on Apple).
- Apple Silicon eligibility: kev-0.8B is validated on all Apple Silicon
  (MLX) and becomes the recommended local option there (DI 23.3 vs Laya
  ~0 zero-shot); kev-4B/9B offered on 32 GB+ Macs, 27B on 96–128 GB.
- `snapdec bench`: fixed 12-item mini-suite (accuracy, Brier, latency,
  decision mix) against the active or mock backend — measured claims now
  come from a command, per AGENTS.md; first (mock) run committed under
  docs/benchmarks/.
- `snapdec models`: real hardware-gated catalog view (starred recs,
  `--all` to peek beyond spec) replacing the stale stub.
- Ephemeral-run guard (§5.3): `uvx snapdec init` now detects the uvx
  cache env, persists a real `uv tool install`, and re-execs from it —
  agent registrations can no longer point into a cache that disappears.
- MCP Registry listing: `server.json` (name `io.github.aktonay/snapdec`,
  test-locked to the shipped version) + `publish-registry.yml` using
  mcp-publisher with GitHub OIDC.
- Skill v2: `ask` tool documented, complete failure-reason list, version
  marker, and two full examples (payload + sample output + walkthrough)
  under `skills/snapdec/examples/`.

### Fixed
- OpenRouter hosted path was broken: kev model ids were delisted
  upstream; the default chain is now the only live id
  (`typesafe/jev-router`) with a regression test against dead ids.
- "slow on CPU" no longer mislabels Kev on Apple Silicon (MLX is fast).
- `snapdec init --backend local` with no model now defaults per backend
  (kev → `jaredpalmer/kev-0.8b`) instead of sending laya's "english".
- Catalog stats updated to Kev 1.0 held-out numbers (breadth-v1) on one
  consistent scale; Jev reference updated 51.67 → 54.0.

### Deferred
- Windows managed-kev 1.0 install not re-verified on real hardware;
  daemon version-skew compare; Windsurf/Cline skill dirs; calibration
  refit; macOS real-hardware verification of the MLX path.

## [0.2.0] — 2026-10-03

### Added
- First-run wizard with hardware-gated model catalog and honest stats
  (Decision Index / OOD accuracy / latency / setup size); only options the
  machine can actually run are listed; Kev-4B requires 12 GB VRAM, Kev-0.8B
  flagged `slow on CPU` without a CUDA GPU.
- Managed local provisioning, fully automatic after choice: runtime venv,
  install, weight download, server launch (127.0.0.1 only). Supports Laya
  (`laya[serve]`, PyPI) and Kev (pinned git tarball — not on PyPI).
- Hosted path: paste any key — provider auto-detected from key format;
  OpenAI/Groq/Anthropic keys get a clear incompatibility hint instead of a
  silent misroute; model auto-picked free-variant-first with paid fallback.
- Agent registration resolves the absolute command (fixes bare-`snapdec`
  entries that failed when the venv wasn't on PATH); Claude Code entries are
  refreshed idempotently on re-init.
- Fan-out for classify/score/rank: one request per item, parallel (§4.6) —
  small-context backends can no longer collapse N items into one answer.
- Daemon: port fallback for concurrent instances; `/shutdown` no longer
  token-gated (loopback bind is the boundary; fixes stale-daemon deadlock).
- JSONC-tolerant verify for agents whose configs carry comments
  (Antigravity) — writing commented files is still refused.

### Fixed
- Laya wire compat: `noul` arrives as P(yes) float (not bool); `/models`
  endpoint (not `/v1/models`); non-empty `instructions` required.

## [0.1.0] — 2026-10-03

- Initial Phase 1 scaffold: MCP v2 shim + shared daemon, tier-0
  `project_facts`, mock + remote `/v1/systemone` backends, 9 agent
  integrators (CLI-first, backup-first, atomic, exactly reversible),
  fail-closed decision envelopes, wizard, doctor, uninstall.
