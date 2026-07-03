# Model Context Protocol (MCP) Integration

Google Antigravity's Go `language_server` has **native** support for the Model Context Protocol (MCP). MCP servers are registered directly in the server's native configuration file `mcp.json`, and the Go server orchestrates communications, tool resolution, and execution natively.

This completely eliminates the need for any custom proxy-level tool shims or interceptors, allowing tools to be natively surfaced in chat.

---

## Registered MCP Servers

On the Web Hub VM, MCP servers are registered inside `~/.gemini/antigravity/mcp.json` (pointing to their executables and arguments). The following three servers are configured:

### 1. Google Workspace MCP (`google_workspace`)
A Node-based MCP server that interacts directly with Google Workspace APIs (Calendar, Gmail, Drive, Sheets) using secure, headless OAuth.
- **Tools exposed:**
  - `gmail_list_messages` / `gmail_send_email`
  - `calendar_list_events` / `calendar_create_event`
  - `drive_list_files`
  - `sheets_create_spreadsheet`
- **Configuration in `mcp.json`:**
  ```json
  "google_workspace": {
    "command": "node",
    "args": ["/home/admin_mgenchev_altostrat_com/my-mcp-server/index.js"]
  }
  ```

### 2. Deep Research MCP (`deep_research`)
A Python FastMCP server that executes intensive multi-turn research loops against Vertex AI and DuckDuckGo search.
- **Tools exposed:**
  - `deep_research(query, mode)`
- **Configuration in `mcp.json`:**
  ```json
  "deep_research": {
    "command": "python3",
    "args": ["/mnt/data/antigravity/bin/mcp_deep_research.py", "--port", "8093"]
  }
  ```

### 3. Native Filesystem MCP (`filesystem`)
Exposes standard filesystem manipulation actions, scoped to the projects directory.
- **Configuration in `mcp.json`:**
  ```json
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/mnt/data/projects"]
  }
  ```

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
