# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
