# Spike S4 — MCP Python SDK v2 skeleton (✅ verified 2026-10-03)

Environment: Windows 11, Python 3.12.10, `mcp==2.3.0` (pip).

## Findings

| Question | Result |
|---|---|
| v2 import path | `from mcp.server.mcpserver import MCPServer` — `FastMCP` is **gone** (`mcp.server.fastmcp` raises with migration pointer) |
| Constructor | `MCPServer(name=…, instructions=…)` |
| Tool registration | `@server.tool(name=…, description=…)` decorator; sync functions run in a worker thread automatically |
| Serving stdio | `server.run("stdio")` |
| In-memory test client | `from mcp import Client` → `async with Client(server) as client:` — first-class, no streams wiring needed |
| `list_tools()` | returns `ListToolsResult`; the list is **`result.tools`** (iterating the result itself yields a `(tools, meta)` tuple — gotcha) |
| `call_tool(name, args)` | returns `CallToolResult`; plain-dict returns arrive as `TextContent` JSON (no `structured` attr) |
| Startup | shim imports no ML deps → < 1 s (import cost ≈ mcp + httpx only) |

## Gotchas hit (fixed in-code)

1. **Tool-name shadowing:** decorating a function named `project_facts` while
   importing a function of the same name → silent infinite recursion. Import
   under an alias (`_project_facts`) and keep tool `name=` explicit.
2. Windows console cp1252 cannot print `✓`/`✗` via rich legacy renderer —
   CLI uses ASCII markers (`[ok]`/`[FAIL]`).

## DoD

- [x] Minimal MCPServer with tools registered — `src/sysone/mcp/server.py`
- [x] In-memory Client test — `tests/contract/test_mcp_server.py` (6 tools,
      project_facts round trip, fail-closed envelope, live daemon call)
- [x] Startup < 500 ms (no heavy imports in shim path)
- [ ] Register in Claude Code via `claude mcp add --scope user` + transcript
      of a real tool call — pending owner consent on this dev machine
