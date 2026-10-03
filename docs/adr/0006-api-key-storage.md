# ADR-0006: API key storage — env-var reference or 0600 file, never agent configs

Date: 2026-10-03 · Status: accepted (implements §9.1)

## Context
`jev-code` copies keys into each harness config because some harnesses filter
the environment — a leak surface we refuse.

## Decision
Keys live only in sysone's own state: an **env-var name** (no secret stored)
preferred, or a 0600 `state/keys` file fallback. Only the daemon reads them;
the shim and agents never see a key. `doctor` shows masked hints only.

## Consequences
- OS-keychain (`keyring`) upgrade path stays open; file mode is the portable
  v0.
- `--api-key-env VAR` mode stores zero secrets — CI friendly.
- Rotating a key = update env var or re-run `sysone init`; no agent configs
  to chase.
