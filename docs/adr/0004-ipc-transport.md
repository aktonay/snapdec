# ADR-0004: IPC transport — UDS on Unix, loopback TCP + token on Windows

Date: 2026-10-03 · Status: accepted (implements §4.4)

## Context
Shim↔daemon IPC must be local-only and authenticated; Windows has no
practical UDS for Python stdlib http.server.

## Decision
- macOS/Linux: AF_UNIX socket at `$XDG_RUNTIME_DIR/sysone.sock` (else state
  dir), 0600.
- Windows: `127.0.0.1:48712` + 256-bit bearer token in `state/daemon.json`
  (0600). Never binds non-loopback; `--serve-team` (Phase 4) would require
  TLS + explicit opt-in.

## Consequences
- Same wire contract either way (`/healthz`, `/v1/systemone`), so backends
  are interchangeable and `kev.serve`-compatible.
- Port collision handled at bind time (OS assigns on failure → error, no
  silent fallback); token check on every POST except /healthz.
