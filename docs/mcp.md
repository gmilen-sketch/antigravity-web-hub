# MCP integration

The proxy speaks the Anthropic messages/tools API to Vertex, but exposes an
MCP shim so any FastMCP tool can be surfaced to Claude cascades running in
the hub. Today one MCP ships: `deep-research`. Adding a second is ~50 lines.

## Deep-research MCP

Server: `src/mcp_deep_research.py` (Python, FastMCP 3.x, Streamable HTTP + SSE).

- Started on demand from chat: type `/mcp start` in the input.
- One tool exposed: `deep_research(query, mode)`.
- `mode="standard"` — 5 tool turns, 4k tokens, ≤ 3 fetches, ≤ 2 searches.
- `mode="max"` — 15 tool turns, 16k tokens, ≤ 12 fetches, ≤ 8 searches.
- Internally uses Claude Opus 4.8 via Vertex + its own copies of `fetch_url`
  and `web_search` (identical SSRF hardening).
- Auth: prefers ADC (via `google.auth.default`), falls back to
  `ANTHROPIC_API_KEY` env var.
- Runs on `127.0.0.1:8093` by default; override with
  `MCP_DEEP_RESEARCH_PORT`.

## Slash-command lifecycle (implemented in proxy.py)

```
User types: /mcp start
    ↓
proxy.py SendUserCascadeMessage handler intercepts before Vertex call
    ↓
_mcp_start() forks: python3 mcp_deep_research.py --port 8093
    ↓
waits up to 8s for :8093 to open
    ↓
records CLAUDE_CASCADES entry response = "✅ started (pid=…)"
```

While the MCP is running, `DEEP_RESEARCH_TOOL_SCHEMA` is appended to
`CLAUDE_TOOLS` on every Vertex call, so Claude sees it in the tool list.

## When Claude calls the tool

`_execute_tool("deep_research", …)` opens a FastMCP client
(`StreamableHttpTransport`) to `http://127.0.0.1:8093/mcp`, calls the tool,
returns the answer text (plus a small "[deep_research: standard, N turns,
tools: K]" footer for debug).

Timeout: 180s for standard mode, 600s for max.

## Adding your own MCP

1. Write a FastMCP server (Python or TS). Expose your tool.
2. Add a schema entry to `proxy.py`:

```python
MY_TOOL_SCHEMA = {
  "name": "my_tool",
  "description": "…",
  "input_schema": {"type":"object", "properties":{…}, "required":[…]},
}
```

3. In `_call_vertex_claude`, add it to `tools` when appropriate (mirror the
   `_mcp_running()` gate pattern).

4. In `_execute_tool`, add a dispatch branch:

```python
if name == "my_tool":
    return await _call_mcp_my_tool(inp)
```

5. In `SendUserCascadeMessage`'s slash-command block, add
   `/my start | stop | status` handlers (or reuse the `/mcp` block).

6. If you want the tool to be lazily-launched, mirror `_mcp_start()` — fork
   the subprocess, wait for its port.

That's it — the SPA has no visibility into the MCP itself; it just sees the
tool as one more thing Claude can call.

## Debugging

- MCP subprocess stdout/stderr goes to `/dev/null` by default in
  `_mcp_start()`. Change to `subprocess.PIPE` or a file path if you need
  logs.
- Slash-command responses render directly in the chat (no Vertex round-trip).
- The MCP's own tool loop calls `_call_claude` → same 500 error format on
  Vertex 4xx as the main proxy.
