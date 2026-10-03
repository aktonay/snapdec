# Recipes

## CI failure triage (40 failures)
Paste each failure block as an item; classes:
`infrastructure` (flaky runner, network, disk), `real_bug`, `environment`
(missing dep, wrong version), `timeout`, `other`.
Act on `auto` items in bulk; read `review` items yourself.

## File picking (issue → files)
`rank(query=issue text+title, candidates=[{id:path, text:path + exported symbols}])`.
Feed top_k to your normal search flow.

## Error classification
`check(evidence=stack trace, checks={is_network: "caused by network access?",
is_permission: "caused by missing permissions?"})`.

## Diff vs description
`check(evidence=diff, checks={implements: "does this diff implement the stated intent?"})`.

## Severity scoring
`score(items=open PRs, levels=["trivial","minor","major","critical"])`.
