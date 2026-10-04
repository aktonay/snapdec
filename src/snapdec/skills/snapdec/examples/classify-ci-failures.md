# Example — classify CI failures

Input (40 failures trimmed to 3):

```json
{
  "items": [
    {"id": "t1", "text": "Tests failed: OSError network unreachable on runner"},
    {"id": "t2", "text": "AssertionError: expected status 200, got 500"},
    {"id": "t3", "text": "ModuleNotFoundError: No module named requests"}
  ],
  "classes": {
    "infra": "network/runner problem",
    "bug": "real code bug",
    "deps": "missing dependency"
  }
}
```

Tool call: `classify(items, classes)`

```json
{
  "results": [
    {"id": "t1", "label": "bug",  "probability": 0.73, "decision": "review"},
    {"id": "t2", "label": "bug",  "probability": 0.94, "decision": "auto"},
    {"id": "t3", "label": "deps", "probability": 0.61, "decision": "review"}
  ],
  "summary": {"items": 3, "auto": 1, "review": 2}
}
```

Walkthrough:
- `t2` is `auto` with p=0.94 → act in bulk (file as code bug) without reading it again.
- `t1` and `t3` are `review` → read those two yourself and decide; don't guess.
- Report: "1 failure auto-triaged as bug by snapdec (p=0.94); 2 reviewed manually."
  (Rule 6 — disclose model-driven actions.)
