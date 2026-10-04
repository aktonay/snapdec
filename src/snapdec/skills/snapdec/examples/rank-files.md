# Example — rank files against an issue

Input:

```json
{
  "query": "Fix: login returns 500 when session cookie missing",
  "candidates": [
    {"id": "src/auth/session.py", "text": "src/auth/session.py — load_session, SessionError, cookie parse"},
    {"id": "src/db/pool.py", "text": "src/db/pool.py — connection pool, retries"},
    {"id": "tests/test_login.py", "text": "tests/test_login.py — login flow, 500 assertions"}
  ]
}
```

Tool call: `rank(query, candidates, top_k=2)`

```json
{
  "results": [
    {"id": "src/auth/session.py", "probability": 0.91, "decision": "auto"},
    {"id": "tests/test_login.py", "probability": 0.58, "decision": "review"}
  ],
  "summary": {"items": 3, "auto": 1, "review": 1}
}
```

Walkthrough:
- Start the fix from `src/auth/session.py` (auto, p=0.91).
- `tests/test_login.py` is review — read it yourself before deciding it matters.
- Feed the top_k to your normal search/reading flow; ranking narrows, it doesn't replace reading.
