# Antigravity Web Hub

An enterprise-ready, headless GCP VM deployment and architecture for Google Antigravity Web, featuring native optimizations, multi-model routing, and robust API integrations.

---

## 📌 Project Overview (What This Project Is About)

**Antigravity Web Hub** is an optimized, security-hardened, and production-ready distribution of Google's [Antigravity (AGY)](https://antigravity.google/) web platform tailored for cloud environments. It transforms Antigravity from a desktop-centric CLI and local GUI tool into a persistent, multi-user web-accessible workspace. 

Running on a headless Google Cloud Platform (GCP) VM (`jumpstation`), the Web Hub serves Antigravity’s beautiful Single Page Application (SPA) to remote teams, protected by an Identity-Aware Proxy (IAP) and a GCP Classic HTTPS Load Balancer with Google-managed SSL.

### Key Capabilities Included:
- **🔄 Optimized Native Routing:** Zero-latency direct-to-Go streaming, bypassing bulky intermediate proxies for high-throughput gRPC-Web RPCs.
- **🛡️ Enterprise Security:** Google Single Sign-On (SSO) and IAP out of the box, with automatic token-based authentication and secure loopback controls.
- **🔌 Native Google Workspace MCP Server:** Asynchronous operations with Google Gmail, Drive, Sheets, and Calendar without client browser dependencies.
- **⚡ On-demand Deep Research:** Native FastMCP server running highly intensive agentic research loops using Gemini.
- **🎨 Custom Model Droplist:** A clean UI dropdown offering selection of Google Gemini models (3.5 Flash, 3.1 Pro, etc.) with automated Vertex AI translation.

---

## 💡 Why We Built Antigravity Web

While Google Antigravity is a groundbreaking agentic framework, its out-of-the-box experience is designed for local desktop development (using loopbacks like localhost). Transitioning Antigravity to a remote, collaborative, or enterprise setting introduced several core challenges that **Antigravity Web Hub** solves:

### 1. Persistent, Long-Running Agent Workspaces
Local desktop execution ties the agentic process to your machine’s power state and network connection. When utilizing long-running execution commands (like the `/goal` command), you need a persistent, headless remote server. The Web Hub runs on a dedicated VM, allowing cascades to execute overnight or in the background without interruptions.

### 2. Resolving Remote Model API Limitations
In "external builds" or headless remote environments, Antigravity's direct client-side Gemini communication path is prone to failure (e.g., throwing `GetChatMessage is unimplemented` errors). We resolved this by routing all model interactions through a local sidecar that safely wraps, cleans, and translates standard agent payloads into standard Vertex AI API calls.

### 3. Native Integration with Google Workspace
Instead of relying on browser-based OAuth flows or local user sessions, our architecture integrates a server-side Node-based Google Workspace MCP server using service accounts or a secure headless OAuth flow. This allows your agent to read emails, write spreadsheets, and schedule calendar meetings directly on the cloud server.

### 4. Zero-Latency Streaming Under Load
Serving a complex real-time SPA over a load balancer often results in proxy timeouts or HTTP/2 protocol resets (such as `ERR_HTTP2_PROTOCOL_ERROR` or RST_STREAM errors) when using standard WSGI/ASGI proxies. We built a direct-to-Nginx routing matrix that serves static assets and high-frequency streaming events with zero intermediate hops.

---

## 🏗️ High-Level Architecture (How It Is Built)

The architecture is built for maximum reliability, absolute security, and minimum latency. It is divided into three primary layers: **Access Layer**, **Routing & Orchestration**, and **Model / Tool Integration**.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          1. Access Layer                               │
│  User Browser ───[ HTTPS / Google SSO ]───► GCP Load Balancer (IAP)     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ h2
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          2. Routing & Orchestration (Nginx)            │
│                 ┌────────────── Nginx :8080 ──────────────┐            │
│                 │                                         │            │
│  /GetUserStatus │ /StartCascade            Streaming RPCs │ Assets     │
│                 ▼                                         ▼            │
│         ccpa_mock.py :8083                      language_server :8081  │
│      (Python sidecar & Vertex)                  (Go native SDK)        │
└─────────────────┬─────────────────────────────────────────┬────────────┘
                  │                                         │
┌─────────────────┼─────────────────────────────────────────┼────────────┐
│                 │        3. Models & Tools Integration    │            │
│                 ▼                                         ▼            │
│         Vertex AI API                          Native MCP Configuration│
│   (streamGenerateContent)                      ├── google_workspace    │
│                                                └── deep_research       │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown:

1. **GCP Classic HTTPS Load Balancer (IAP Protected):**
   Acts as the single public entry-point (via `https://antigravity.customertests.info/`). Google Identity-Aware Proxy (IAP) handles user authentication and blocks any unauthorized requests before they ever reach the VM.
2. **Nginx Reverse Proxy (`:8080`):**
   Handles the intelligent path routing:
   - **Streaming/Asset Traffic:** High-performance real-time RPCs (like `StreamAgentStateUpdates`) and client-side SPA files route directly to Google's native Go `language_server` on port `8081`.
   - **Control/API Traffic:** Requests like `GetUserStatus` and `StartCascade` are proxied to `ccpa_mock.py` on port `8083` to inject custom model dropdown items and establish cascade configurations.
3. **Native Go `language_server` (`:8081`):**
   The core engine from Google's public Antigravity SDK. It runs in `--standalone` and `--subclient_type=hub` modes. It hosts the real chat trajectories, maintains SQLite conversational databases (`~/.gemini/antigravity/conversations/`), and orchestrates the MCP servers.
4. **Python Sidecar `ccpa_mock.py` (`:8083`):**
   A lightweight, FastAPI-free Python process that provides:
   - Dynamic injection of custom model configs in the dropdown list (e.g., Gemini 3.5 Flash, 3.1 Pro, etc.).
   - Model request translation to remove incompatible keys.
   - Live streaming proxying to Vertex AI via Google Application Default Credentials (ADC).
5. **Native MCP Servers:**
   The `language_server` manages tool execution natively via `mcp.json`:
   - `google_workspace` (Node.js): Direct headless integration with Drive, Sheets, Gmail, and Calendar.
   - `deep_research` (Python FastMCP): Exposes structured internet research capabilities using Google Gemini and web-search scrapers.


## Prerequisites

- A Debian/Ubuntu VM in GCP with:
  - Application Default Credentials configured
    (`gcloud auth application-default login` — see [SETUP.md](SETUP.md))
  - A publicly-reachable hostname / IP (the setup script wires up a Classic HTTPS Load Balancer + IAP)
  - A second data disk **strongly recommended** — boot disk fills up fast. The install script formats and mounts it at `/mnt/data` if present.
- Antigravity CLI installed (`~/.gemini/antigravity/bin/language_server`, `agy`). The install script fetches the public installer.

## Installation & Deployment

For a zero-friction, automated deployment from your local workstation, or for step-by-step manual setup instructions, please see the comprehensive **[SETUP.md](SETUP.md)** guide.

### Quick Start (One-Shot Bootstrap)

The quickest way to deploy the entire Web Hub (VM, Load Balancer, SSL certs, and IAP Auth) is using our one-shot workstation orchestrator:

```bash
# 1. Clone the repository
git clone https://github.com/gmilen-sketch/antigravity-web-hub.git
cd antigravity-web-hub

# 2. Configure your environment
cp .env.example .env
nano .env

# 3. Provision and deploy
./scripts/bootstrap_all.sh
```

For more details on OAuth configurations, systemd administration, or advanced GCP VM customization, refer to **[SETUP.md](SETUP.md)**.

## Using it

- **Pick a model** from the dropdown (bottom-right of the input). Gemini models route directly through the native Go server to Vertex AI.
- **Run Google Workspace actions** — Ask Gemini to list drive files, send emails, or check calendar events.
- **Conversations persist.** Restart `antigravity-web.service` — your Gemini cascades come back from agy's own SQLite store.

## Docs

- **[SETUP.md](SETUP.md)** — Step-by-step deployment guide & Workspace OAuth setup
- [ARCHITECTURE.md](ARCHITECTURE.md) — Component diagram and design details
- [docs/request-flow.md](docs/request-flow.md) — End-to-end walkthrough of one turn
- [docs/mcp.md](docs/mcp.md) — Adding your own MCP tools
- [docs/custom-domain.md](docs/custom-domain.md) — Swapping `<ip>.nip.io` for a real DNS domain
- [docs/troubleshooting.md](docs/troubleshooting.md) — Known failure modes and operations runbook

## Contributions & scope

The project is intentionally small and lightweight — a simple Nginx configuration, a sidecar Python process, and a systemd unit. If you want to add or modify model settings, follow the pattern in `src/ccpa_mock.py`'s `DROPDOWN_MODELS` and `map_model_name`.

## License

MIT — see [LICENSE](LICENSE).
