# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
