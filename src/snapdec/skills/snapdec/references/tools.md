# Tool contracts

## project_facts(path) → {facts, evidence, confidence}
Deterministic (Tier 0). `facts`: languages, test_cmd, lint_cmd, typecheck_cmd,
build_cmd, package managers, monorepo_layout, ci_provider. Evidence = files read.

## classify(items, classes, instructions?)
`items: [{id, text}]`, `classes: {label: description}`.
Per item: `label`, `probability`, `margin`, `probabilities`, `decision`.

## check(evidence, checks)
`checks: {name: question}`. Per check: `verdict: yes|no|uncertain`, probability, decision.

## score(items, levels)
`levels: [2..10]` low→high descriptions. Per item: `score`, `nearest_level`, decision.

## rank(query, candidates, top_k?)
`candidates: [{id, text}]`. Sorted `results`, `any_relevant`.

## ask(state, questions)
Raw System One passthrough. `questions: {name: {type: choice|noul|score,
instructions, criteria?}}` — mixed types in one call. Prefer the typed
tools above; `ask` is for cases they don't cover (custom question shapes,
several different questions about one state).

## Envelope
```
{results:[…], summary:{items,auto,review}, policy:{auto_accept,min_margin},
 backend:{name,latency_ms,…}, truncated, warnings}
```
Failure (never throws): `{results:[], decision:"review", reason, hint}`.
Reasons: `no_model | warming | timeout | no_backend | oversize | error`.
