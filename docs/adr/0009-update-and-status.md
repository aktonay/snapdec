# ADR-0009: Update mechanism + answer status footer

Date: 2026-10-04 · Status: accepted

## Context

Users install once and expect the wiring to keep working across upgrades,
and want to see (quietly) what snapdec did after each decision.

## Decisions

1. **Notice-only automation.** `init`/`doctor` fetch the latest version
   from `https://pypi.org/pypi/snapdec/json` (GET of public metadata —
   nothing about the user is sent, so the §0.5 no-telemetry rule holds)
   and cache it 24 h in `state/update_check.json`. Upgrade itself is an
   explicit `snapdec update` (`uv tool install --upgrade` → pip → pipx).
   Silent auto-install is refused: it violates the consent rule and can
   swap a working tool mid-session.
2. **Skill refresh on upgrade**: skill copies in agent dirs are refreshed
   by re-running `snapdec init` (documented in the update output), not
   mutated in the background — agents own those dirs.
3. **Status footer**: every Tier-1 envelope carries
   `status: "· snapdec <v> · <model> · <ms> · <auto>/<n> · ~N tok offloaded"`.
   Offloaded estimate = chars(state)/4 — tokens processed by the decision
   model instead of the host LLM; labeled "offloaded" (not "saved") because
   real savings depend on the host's behavior. Informational field only;
   agents must not parse it.
4. **Always-on**: unchanged lazy start — the MCP shim starts the daemon on
   first tool call and the daemon resurrects a dead managed backend
   (`provision.ensure_running`). No background services, no boot hooks.

## Consequences

- Offline machines: check silently no-ops; every command works.
- uv tool vs pip installs: upgrade path tries the install method that
  exists; mixed installs fall back with a clear failure message.
