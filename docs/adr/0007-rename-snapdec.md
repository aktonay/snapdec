# ADR-0007: Project name → `snapdec`

Date: 2026-10-03 · Status: accepted (closes the rename gate §1.4 / §17.1)

## Context
`sysone` was a placeholder. Requirements: available on PyPI, npm and GitHub;
no trademark friction ("Jev"/"TypeSafe" banned; "Agent S"/"S1" = Simular AI;
"reflex" = large existing project). Real English candidates (blink, hunch,
glimpse, gauge, verdict, squint, trice, jiffy, prethink …) were all taken on
PyPI and/or npm.

## Decision
**`snapdec`** — "snap decision": exactly the System One concept (fast,
automatic judgment) in two syllables. CLI reads well: `snapdec init`,
`snapdec doctor`, `snapdec classify`.

Availability, verified 2026-10-03:
- PyPI `snapdec`: HTTP 404 (free)
- npm `snapdec`: HTTP 404 (free)
- GitHub search `snapdec in:name`: only trivial repos (≤ 6 stars)
- MCP Registry: namespace `io.github.<owner>/snapdec` — publish-time check
  still required (registry verifies via README marker)

Owner chose `snapdec` over `singlepass`, `verdicto`, `gutcall`.

## Consequences
- Rename executed as a single commit (`_brand.py` NAME + `pyproject.toml` +
  package dir + skill name). `SNAPDEC_HOME` replaces `SYSONE_HOME`.
- Historical docs (`SYSONE_ARCHITECTURE.md`) keep the placeholder name.
- README carries the `mcp-name:` marker only at publish time.
