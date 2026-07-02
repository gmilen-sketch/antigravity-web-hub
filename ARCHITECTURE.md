# Architecture

```
                              ╔════════════════════════════════════════════════════╗
                              ║  USER'S BROWSER                                    ║
                              ║  https://<your-hostname>/                          ║
                              ╚════════════════════════════════════════════════════╝
                                                    │
                                       HTTPS + IAP-authenticated cookie
                                                    ▼
                              ┌────────────────────────────────────────────────────┐
                              │  GCP Classic HTTPS Load Balancer                   │
                              │  • forwarding rule → jumpstation VM :443           │
                              │  • backendService timeoutSec=86400 (long streams)  │
                              │  • IAP OAuth (Google-managed)                      │
                              └────────────────────────────────────────────────────┘
                                                    │  h2
                                                    ▼
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║  Debian/Ubuntu VM                                                                                        ║
║                                                                                                          ║
║  ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐  ║
║  │  nginx :8080                                                                                       │  ║
║  │  routing by path:                                                                                  │  ║
║  │    ├── streaming RPCs → language_server :8081  (chunked, no buffering)                             │  ║
║  │    │   (StreamAgentStateUpdates, JetboxSubscribeTo*, ProjectUpdatesStream)                         │  ║
║  │    └── everything else → proxy.py :8082                                                            │  ║
║  └────────────────────────────────────────────────────────────────────────────────────────────────────┘  ║
║           │                                                        │                                     ║
║           │ streams                                                │ HTML, auth mocks, cascade RPCs      ║
║           ▼                                                        ▼                                     ║
║  ┌──────────────────────────────────┐         ┌──────────────────────────────────────────────────────┐   ║
║  │  language_server (Antigravity    │◀────────│  proxy.py  (FastAPI, port 8082)                      │   ║
║  │  SDK — Go, hub mode)             │  gRPC   │                                                      │   ║
║  │                                  │  46693  │  Responsibilities per path:                          │   ║
║  │  --http_server_port=8081         │         │   • auth mocks (GetUserStatus, HasAuthToken, …)      │   ║
║  │  --model_api_client_type=gemini  │         │   • model dropdown injection (append CLAUDE_MODELS   │   ║
║  │  --override_model_name=          │         │       to GetUserStatus response)                     │   ║
║  │      gemini-3.5-flash            │         │   • inject <script> into index.html                  │   ║
║  │  --cloud_code_endpoint=          │◀────auth│       (nativeStorage polyfill, model-picker bridge,  │   ║
║  │      http://127.0.0.1:8082       │  mocks  │        fetch wrapper adds x-user-model header)       │   ║
║  │  --standalone                    │         │   • Claude shim (x-user-model=Opus/Fable OR          │   ║
║  │  serves the SPA (main.js)        │         │        cid ∈ CLAUDE_CASCADES → sticky-route)         │   ║
║  │  serves /c/{cid} route           │         │   • /mcp start|stop|status slash commands            │   ║
║  │  supervises real Gemini cascades │         │   • softens "trajectory not found" errors            │   ║
║  │                                  │         │   • proto-level model-enum injection for Gemini      │   ║
║  │  Reads/writes:                   │         │       cascades                                       │   ║
║  │    ~/.gemini/antigravity/        │         │                                                      │   ║
║  │      conversations/*.db          │         │                                                      │   ║
║  │      brain/…/transcript.jsonl    │         │                                                      │   ║
║  └──────────────────────────────────┘         └──────────────────────────────────────────────────────┘   ║
║                                                             │                                            ║
║                                    ┌────────────────────────┼─────────────────────────────┐              ║
║                                    │                        │                             │              ║
║                          Claude shim path            Gemini cascade path         Deep-research           ║
║                            (multi-turn +               (proto injection            (on-demand MCP)       ║
║                             tool loop)                  → language_server)                               ║
║                                    │                        │                             │              ║
║                                    ▼                        ▼                             ▼              ║
║                        HTTPS to Vertex AI             (already through            ┌───────────────────┐  ║
║                        (see External)                  language_server            │ mcp_deep_research │  ║
║                                                        gRPC 46693 above)          │ .py  (FastMCP)    │  ║
║                                                                                   │ :8093 Streamable  │  ║
║                                                                                   │       HTTP + SSE  │  ║
║                                                                                   │                   │  ║
║                                                                                   │ standard/max mode │  ║
║                                                                                   │ own tool loop:    │  ║
║                                                                                   │  fetch_url,       │  ║
║                                                                                   │  web_search       │  ║
║                                                                                   │ (spawned lazily   │  ║
║                                                                                   │  by /mcp start)   │  ║
║                                                                                   └───────────────────┘  ║
║                                                                                             │            ║
║                                                                                    HTTPS to Vertex       ║
║                                                                                                          ║
║  ─── SUPERVISION ─────────────────────────────────────────────────────────────────────────────           ║
║  systemd unit  antigravity-web.service                                                                   ║
║    ExecStart  ~/.gemini/antigravity/bin/start_hub.sh                                                     ║
║                    ├─ python3 proxy.py                                                                   ║
║                    └─ language_server --standalone …                                                     ║
║                                                                                                          ║
║  ─── STORAGE ────────────────────────────────────────────────────────────────────────────────            ║
║  /mnt/data           ext4 on /dev/sdb (recommended)  — persistent Claude cascades                        ║
║    └── antigravity/claude_cascades/{cid}.json   (loaded on boot; survives restart)                       ║
║  ~/.gemini/antigravity/conversations/*.db       — agy's Gemini cascade DBs                               ║
║  ~/.gemini/antigravity/brain/{cid}/…            — trajectory placeholders (auto-provisioned)             ║
║                                                                                                          ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════╝
                                                    │                                    │
                                    ADC access token (Bearer)             DuckDuckGo HTML / arbitrary URLs
                                                    ▼                                    ▼
              ┌────────────────────────────────────────────────┐   ┌─────────────────────────────────────┐
              │  Vertex AI  aiplatform.googleapis.com          │   │  Public web                         │
              │   POST …/publishers/anthropic/models/          │   │   • html.duckduckgo.com/html/       │
              │        {claude-opus-4-8,claude-fable-5}:       │   │   • any http(s) URL, SSRF-guarded   │
              │        rawPredict                              │   │     (RFC1918/link-local blocked)    │
              │   anthropic-version: vertex-2023-10-16         │   └─────────────────────────────────────┘
              │  ADC via `gcloud auth application-default`     │
              └────────────────────────────────────────────────┘
```

## Antigravity binaries in use

We depend only on the **publicly distributed** Antigravity CLI download. No
Google-internal binaries or private endpoints are called; the `exa.*` gRPC
package prefix visible in the code is the language_server's public wire
protocol.

| Binary | Package | Role |
|---|---|---|
| `~/.gemini/antigravity/bin/language_server` | Antigravity SDK (bundled with CLI install) | Go binary that speaks `exa.language_server_pb.LanguageServerService`. Serves the hub SPA, owns real Gemini cascades. Started with `--standalone --override_model_name=gemini-3.5-flash`. |
| `~/.gemini/antigravity-cli/bin/agy` | Antigravity CLI | Not run by the service, but present on disk. Installed the SDK. |
| `~/.gemini/antigravity/bin/gcloud`, `webm_encoder` | Bundled with SDK | Utilities. |
| SPA (`main.js`) | Served by `language_server`'s HTTP handler on :8081 | We inject one `<script>` block into `<head>` on the way through the proxy. |

## Custom (non-Google) components in this repo

| Component | Path in repo | Purpose |
|---|---|---|
| Reverse proxy | `src/proxy.py` | FastAPI reverse proxy; the brains of the operation |
| Deep-research MCP | `src/mcp_deep_research.py` | Python FastMCP server (Streamable HTTP + SSE) |
| Node MCP stub | `src/mcp_node_stub/index.js` | Placeholder used by agy-side MCP mechanism |
| Launcher | `config/start_hub.sh` | Supervises `proxy.py` + `language_server` |
| Systemd unit | `config/antigravity-web.service` | Boot / restart / logs |
| Nginx site | `config/nginx.conf` | Path-based routing to the two upstreams |

## End-to-end request flow (typical Claude turn)

1. Browser POSTs `SendUserCascadeMessage` to `https://<hostname>/…`
2. GCP LB → nginx :8080 → proxy.py :8082 (unary RPC, not in the streaming allowlist).
3. Injected JS added `x-user-model: Claude Opus 4.8` header; proxy hits its Claude shim path.
4. proxy.py appends the user turn to `CLAUDE_CASCADES[cid]["turns"]`, persists JSON to `/mnt/data`, kicks off an async `_call_vertex_claude(entry)`.
5. Vertex Anthropic API returns either final text OR `tool_use` blocks (`fetch_url` / `web_search` / `deep_research`).
   - For `deep_research`, proxy makes a **FastMCP HTTP call** to `:8093`, which itself runs its own multi-turn tool loop against Vertex + DuckDuckGo.
6. Loop until Claude returns text → stored on `entry["turns"][-1]["response"]` → persisted to disk.
7. Meanwhile, the SPA's `StreamAgentStateUpdates(cid)` stream (long-lived, held open in proxy.py) polls `entry` every 500 ms; on any change it yields a synthetic `CascadeAgentState` frame back over nginx → LB → browser → React SPA renders the reply.

For a byte-level walkthrough of a single turn, see [docs/request-flow.md](docs/request-flow.md).
For a focused explanation of what a "shim" is and how the Vertex Claude
interception + translation works, see [docs/claude-shim.md](docs/claude-shim.md).
