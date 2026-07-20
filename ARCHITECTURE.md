# Architecture

Google Antigravity Web Hub uses a direct, proxy-less native architecture. The legacy FastAPI-based `proxy.py` and port `8082` have been completely eliminated. Traffic now flows with zero-latency streaming directly through Nginx to the native Go `language_server` process, with only a lightweight Python sidecar (`ccpa_mock.py` on port `8083`) intercepting specific unary paths to perform model list augmentation and routing to Vertex AI.

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
 ║  │    ├── GetUserStatus & StartCascade → ccpa_mock.py :8083 (custom model config & injection)        │  ║
 ║  │    └── All other requests & frontend assets → language_server :8081 (native zero-latency gRPC-Web) │  ║
 ║  └────────────────────────────────────────────────────────────────────────────────────────────────────┘  ║
 ║           │                                                       │                                      ║
 ║           │ frontend assets, streaming RPCs                      │ unary RPCs /v1internal               ║
 ║           ▼                                                       ▼                                      ║
 ║  ┌──────────────────────────────────┐         ┌──────────────────────────────────────────────────────┐   ║
 ║  │  language_server (Antigravity    │◀────────│  ccpa_mock.py (Python sidecar, port 8083)            │   ║
 ║  │  SDK — Go, hub mode)             │         │                                                      │   ║
 ║  │                                  │  POST   │  Responsibilities per path:                          │   ║
 ║  │  --http_server_port=8081         │  /v1    │   • Augment GetUserStatus with the custom Gemini     │   ║
 ║  │  --model_api_client_type=ccpa    │  internal│     model dropdown list (3.5 Flash, 3.1 Pro, etc.)  │   ║
 ║  │  --cloud_code_endpoint=          │  stream │   • Inject DEFAULT_MODEL and configure planner       │   ║
 ║  │      http://127.0.0.1:8083       │  gen    │     settings in StartCascade                         │   ║
 ║  │  --standalone                    │         │   • Forward `/v1internal:streamGenerateContent`      │   ║
 ║  │  serves the SPA (main.js)        │         │     requests directly to Vertex AI                   │   ║
 ║  │  serves /c/{cid} route           │         │   • Fetch and attach ADC tokens                      │   ║
 ║  │                                  │         │                                                      │   ║
 ║  │  Reads/writes:                   │         │                                                      │   ║
 ║  │    ~/.gemini/antigravity/        │         │                                                      │   ║
 ║  │      conversations/*.db          │         │                                                      │   ║
 ║  └──────────────────────────────────┘         └──────────────────────────────────────────────────────┘   ║
 ║                                                             │                                            ║
 ║                                                             ▼                                            ║
 ║                                                     HTTPS to Vertex AI                                   ║
 ║                                                    (see External below)                                  ║
 ║                                                                                                          ║
 ║  ─── NATIVE MCP INTEGRATION ──────────────────────────────────────────────────────────────────           ║
 ║  The language_server natively orchestrates MCP servers configured in `mcp.json`:                         ║
 ║                                                                                                          ║
 ║  ┌──────────────────────────────────┐         ┌──────────────────────────────────────────────────────┐   ║
 ║  │  google_workspace (Node)         │         │  deep_research (Python FastMCP)                      │   ║
 ║  │  Interacts with Google Calendar, │         │  Performs intensive research tasks on-demand via     │   ║
 ║  │  Gmail, Drive, Sheets APIs       │         │  Vertex + DuckDuckGo web searches                    │   ║
 ║  └──────────────────────────────────┘         └──────────────────────────────────────────────────────┘   ║
 ║                                                                                                          ║
 ║  ─── SUPERVISION ─────────────────────────────────────────────────────────────────────────────           ║
 ║  systemd unit  antigravity-web.service                                                                   ║
 ║    ExecStart  ~/.gemini/antigravity/bin/start_hub.sh                                                     ║
 ║                    ├─ python3 ccpa_mock.py                                                               ║
 ║                    └─ language_server --standalone …                                                     ║
 ║                                                                                                          ║
 ║  ─── STORAGE ────────────────────────────────────────────────────────────────────────────────            ║
 ║  ~/.gemini/antigravity/conversations/*.db       — agy's Gemini cascade DBs                               ║
 ║  ~/.gemini/antigravity/mcp_config.json          — client MCP configurations                             ║
 ║                                                                                                          ║
 ╚══════════════════════════════════════════════════════════════════════════════════════════════════════════╝
                                                             │
                                             ADC access token (Bearer)
                                                             ▼
                                       ┌────────────────────────────────────────────────┐
                                       │  Vertex AI  aiplatform.googleapis.com          │
                                       │   POST …/projects/{PROJECT_ID}/locations/global│
                                       │        /publishers/google/models/              │
                                       │        {model}:streamGenerateContent           │
                                       │  ADC via `gcloud auth application-default`     │
                                       └────────────────────────────────────────────────┘
```

## Antigravity binaries in use

We depend only on the **publicly distributed** Antigravity CLI download. No Google-internal binaries or private endpoints are called; the `exa.*` gRPC package prefix visible in the code is the language_server's public wire protocol.

| Binary | Package | Role |
|---|---|---|
| `~/.gemini/antigravity/bin/language_server` | Antigravity SDK (bundled with CLI install) | Go binary that speaks `exa.language_server_pb.LanguageServerService`. Serves the hub SPA, owns real Gemini cascades. Started with `--standalone --model_api_client_type=ccpa --cloud_code_endpoint=http://127.0.0.1:8083`. |
| `~/.gemini/antigravity-cli/bin/agy` | Antigravity CLI | Not run by the service, but present on disk. Installed the SDK. |
| `~/.gemini/antigravity/bin/gcloud`, `webm_encoder` | Bundled with SDK | Utilities. |
| SPA (`main.js`) | Served by `language_server`'s HTTP handler on :8081 | Nginx performs dynamic onboarding bypass by injecting `window.nativeStorage` directly. |

## Custom (non-Google) components in this repo

| Component | Path in repo | Purpose |
|---|---|---|
| Sidecar Mock | `src/ccpa_mock.py` | Lightweight Python sidecar; handles model dropdown configs, StartCascade augmentation, and Vertex AI API stream translation. |
| Deep-research MCP | `src/mcp_deep_research.py` | Python FastMCP server configured natively in `mcp.json` |
| Google Workspace MCP | `src/mcp_google_workspace/` | Node-based MCP server providing actions for Calendar, Gmail, Sheets, and Drive, configured in `mcp.json` |
| Launcher | `config/start_hub.sh` | Supervises `ccpa_mock.py` + `language_server` with proper lock cleaning and loopback configuration |
| Systemd unit | `config/antigravity-web.service` | Boot / restart / logs |
| Nginx site | `config/nginx.conf` | Path-based routing to Go backend and sidecar |

## End-to-end request flow (typical Gemini turn)

1. Browser requests pages or resources. Nginx bypasses onboarding natively by injecting a `window.nativeStorage` polyfill into the HTML `<head>`.
2. When the user loads the app, the browser requests `/exa.*GetUserStatus`. Nginx intercepts this request and proxies it to `ccpa_mock.py` on port `8083` to append Gemini 3.5 Flash, 3.1 Flash Lite Preview, and 3.1 Pro to the client model configurations.
3. When the user starts a chat session, `/exa.*StartCascade` is intercepted by Nginx and routed to `ccpa_mock.py` on port `8083` to inject model details, matching what the Go backend expects.
4. All high-throughput streaming RPCs (like `StreamAgentStateUpdates`) and generic traffic are routed **natively and directly** to the Go `language_server` on port `8081` with zero proxy hops or added latency.
5. When executing model queries, `language_server` (having been configured with `--model_api_client_type=ccpa`) sends `/v1internal:streamGenerateContent` requests to the configured sidecar endpoint `http://127.0.0.1:8083`.
6. `ccpa_mock.py` on port `8083` intercepts this call, cleans up any incompatible keys from the payload, fetches a fresh Google Application Default Credentials (ADC) Bearer token, and forwards the stream via standard Server-Sent Events (SSE) to Vertex AI (`aiplatform.googleapis.com`).
7. Vertex AI returns SSE tokens which are piped back seamlessly to the language server.

For a focused explanation of how the request flow works under the hood, see [docs/request-flow.md](docs/request-flow.md).
