# Model Context Protocol (MCP) Integration

Google Antigravity's Go `language_server` has **native** support for the Model Context Protocol (MCP). MCP servers are registered directly in the server's native configuration file `mcp.json`, and the Go server orchestrates communications, tool resolution, and execution natively.

This completely eliminates the need for any custom proxy-level tool shims or interceptors, allowing tools to be natively surfaced in chat.

---

## Registered MCP Servers (8 Native Servers)

On the Web Hub VM, MCP servers are registered inside `~/.gemini/antigravity/mcp_config.json` (templated from `config/mcp_config.json`). All 8 servers are active out of the box:

### 1. Knowledge Graph MCP (`knowledge_graph` — `src/mcp_knowledge_graph.py`)
Bitemporal Knowledge Graph (`t_valid`, `t_invalid`, `t_tx`) with 6-Field BM25F (`k1=1.2`, `b=0.75`) and 2-hop Personalized PageRank (`PPR`) retrieval.

### 2. Autonomy Engine MCP (`autonomy_engine` — `src/mcp_autonomy_engine.py`)
Exposes the 14 Clean-Room Autonomy Pillars: Bayesian Self-Grill (`C0..C3`), Six Thinking Hats Delphi Router, `P0`/`P1` Quality-First Circuit-Breakers (`P1-CB-8` PICC Firewall), UI Geometry Auditor, and Black-Hat 2-Stage Goldfish → Judge verification.

### 3. Diagram Renderer MCP (`diagram_renderer` — `src/mcp_diagram_renderer.py`)
Compiles GCP Draw DSL (`card` / `connect`), BENTO (`v15.5`), and Mermaid definitions into zero-overlap quadratic Bezier (`Q`) SVG and PNG diagrams.

### 4. Headless Browser CDP MCP (`browser_cdp` — `src/mcp_browser_cdp.py`)
Headless Chromium CDP navigation, DOM/SVG bounding-box inspection, and full-page screenshot capture.

### 5. Cloud Telemetry MCP (`cloud_telemetry` — `src/mcp_cloud_telemetry.py`)
Live BigQuery SQL analytics, Cloud Monitoring time-series queries, and FinOps commitment utilization checks.

### 6. Workspace Docs MCP (`workspace_docs` — `src/mcp_workspace_docs.py`)
3-Tab Inverted-Pyramid (`Arm E`) report generation, `AGENT-SSOT-v1` pointer maps, and 3-Row Staging Diffs (`Baseline` / `Planned` / `Delta`).

### 7. Deep Research MCP (`deep_research` — `src/mcp_deep_research.py`)
Python FastMCP server that executes intensive multi-turn Owl Swarm research loops against Vertex AI (`Gemini 4 Argon` / `Gemini 3.8 Flash`) and web search.

### 8. Google Workspace MCP (`google_workspace` — `src/mcp_google_workspace/`)
Node-based MCP server interacting directly with Google Calendar, Gmail, Drive, Docs, and Sheets APIs using headless OAuth.

---

## Adding Your Own MCP Server

Since the Go backend has standard, native MCP support, adding your own MCP tools is incredibly simple and standard:

1. **Implement your MCP server:** Write your server using any standard SDK (Python FastMCP, Node MCP SDK, Go MCP SDK, etc.).
2. **Copy the files to the VM:** Save your server executable under the home directory or `/mnt/data/antigravity/bin/`.
3. **Add the entry to `mcp.json`:** Open `~/.gemini/antigravity/mcp.json` and add your server definition inside the `mcpServers` object:
   ```json
   "my_custom_tool": {
     "command": "python3",
     "args": ["/mnt/data/antigravity/bin/my_mcp_server.py"]
   }
   ```
4. **Restart the Service:** Restart the service to apply changes and let Go reload the tool definitions:
   ```bash
   sudo systemctl restart antigravity-web.service
   ```

The Go backend will automatically detect the new server on startup, query its exposed tool schemas, and surface them directly to the active Gemini models during chat sessions. No custom coding or proxy modifications are needed!
