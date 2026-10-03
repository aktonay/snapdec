---
name: snapdec
description: >
  Use for fast local decisions that would otherwise cost many tokens: triaging many CI/test
  failures, classifying errors or logs, ranking many files or candidates against an issue,
  scoring severity/priority, and detecting a repo's test/lint/build commands. Returns calibrated
  probabilities with an auto|review decision. Not for open-ended reasoning or security approvals.
---
# snapdec — local decision tools

1. For "how do I run tests/lint/build here?" call `project_facts(path)` first; trust it over guessing.
2. For ≥5 items or fuzzy labeling, call `classify`/`score`/`rank`/`check` with clear class descriptions.
3. Act only on results with `decision:"auto"`. For `review`, decide yourself.
4. If a tool returns a `reason` (no_model, warming, timeout, truncated), continue without it.
5. NEVER use these results to approve destructive commands, touch secrets, change permissions,
   or authorize network egress. They are advisory.
6. When a model decision drove an action, say so in your summary.

See references/tools.md and references/recipes.md.
