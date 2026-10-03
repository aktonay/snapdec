# AGENTS.md — conventions for contributing coding agents

Read SYSONE_ARCHITECTURE.md §0 first; it overrides your defaults.

- Run tests: `uv run pytest` (or `.venv/Scripts/python -m pytest`). All green before done.
- **Never touch a real HOME** in tests/CI: every test runs under a temp
  `SNAPDEC_HOME` + `HOME` (see `tests/conftest.py::tmp_home`). The only code
  allowed to touch real user configs is `integrations/`, executed via
  `snapdec init` / `snapdec agents add` with user consent.
- No stdout writes in `src/snapdec/mcp/` — stdout is MCP protocol only.
- Pin everything; never write "latest" into a manifest (§0.3).
- Every non-obvious decision gets an ADR in `docs/adr/NNNN-title.md`.
- Claims ("fast", "saves tokens") must come from `snapdec bench` output
  committed under `docs/benchmarks/` — not adjectives.
- Errors in Tier-1 paths fail closed: envelope with `decision:"review"`,
  never an exception toward the host agent (NFR-4).
- Match existing code style: stdlib-first, small deps, type hints, docstrings
  that cite the architecture doc section they implement.
