# ADR-0002: Decision tiers (0 / 1 / 2)

Date: 2026-10-03 · Status: accepted (implements §4.3)

## Context
Small models are weak out-of-domain (Kev-0.8B OOD 0.652; Laya zero-shot ≈
random). Pretending otherwise gets users burned.

## Decision
Tier 0 deterministic (project_facts) answers what files can answer; Tier 1
local/remote decision model answers fuzzy classify/rank/score with calibrated
probabilities + `auto|review` abstention; Tier 2 (host frontier model) decides
everything `review`.

## Consequences
- Honest value model (§1.6): the product is a router with abstention.
- `check` never returns an approval; safety-class questions get stricter
  thresholds (decisions/policy.py SAFETY_BONUS).
- Tier-0 quality is load-bearing: needs the golden-file tests it has.
