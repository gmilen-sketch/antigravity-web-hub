# Antigravity Web Hub (v3.1.0 - Stable Release)

[![Release](https://img.shields.io/badge/Release-v3.1.0--Stable-brightgreen.svg)](CHANGELOG.md)
[![Platform](https://img.shields.io/badge/Google%20Cloud-C2%20Compute--Optimized-blue.svg)](https://cloud.google.com/compute/docs/compute-optimized-machines#c2_series)
[![Security](https://img.shields.io/badge/Security-IAP%20Zero--Trust-success.svg)](https://cloud.google.com/iap)

An enterprise-ready, headless GCP VM deployment and architecture for Google Antigravity Web, featuring native optimizations, multi-model routing, and robust API integrations.

---

## 🌟 What's New in v3.1.0

### 1. 🎨 Dynamic Multi-Model Catalog Routing (`src/ccpa_mock.py`)
- **Native UI Dropdown Selection**: Directly switch between cutting-edge Google Gemini and Anthropic Claude models inside the Antigravity chat input:
  - **`Gemini 3.7 Flash`** (`MODEL_GOOGLE_GEMINI_RIFTRUNNER_THINKING_LOW`)
  - **`Gemini 3.6 Flash`** (`MODEL_GOOGLE_GEMINI_2_5_FLASH`)
  - **`Gemini 3.5 Flash Lite`** (`MODEL_GOOGLE_GEMINI_2_5_FLASH_LITE`)
  - **`Claude 3.7 Sonnet`** (`MODEL_ANTHROPIC_CLAUDE_3_5_SONNET`)
  - **`Claude Opus 5`** (`MODEL_ANTHROPIC_CLAUDE_OPUS_4_5`)
  - **`Claude Fable 5`** (`MODEL_ANTHROPIC_CLAUDE_3_5_HAIKU`)
- **Zero-Latency Protocol Translation**: Dynamic request/response mapping to Vertex AI endpoints via Application Default Credentials (ADC) without requiring third-party API keys.

### 2. 🔌 Standard FastMCP Servers Architecture
Auxiliary agent tools are refactored into standard **Model Context Protocol (MCP)** servers running over STDIO JSON-RPC (`transport="stdio"`):
- **`knowledge_graph`** (`src/knowledge_graph/kg_mcp_server.py`): Long-term memory search, concept upsertion, directional edge creation, and compact subgraph extraction.
- **`autonomy_engine`** (`src/autonomy_engine/mcp_autonomy_hub.py`): AAAK 3-pass token compression, 4-voice polyphonic factual retrieval, and context envelope hydration.
- **`deep_research`** (`src/mcp_deep_research.py`): Autonomous agentic research loop with live DuckDuckGo web search and URL parsing.
- **`google_workspace`** (`src/mcp_google_workspace/index.js`): Headless operations with Gmail, Calendar, Drive, and Sheets.

### 3. 🧠 Knowledge Graph Long-Term Memory & 0ms RAM Cache
- **SQLite-WAL Backend**: Bitemporal property graph stored at `~/.gemini/antigravity/knowledge_graph.json` with SQLite write-ahead logging.
- **Shared Memory Cache (`/dev/shm/kg_warm_cache.json`)**: Pre-warmed atomic RAM cache enabling instant, 0ms latency sub-graph context injection for active agent trajectories.

### 4. 🌙 Automated Nightly Dreaming Engine (23:50 UTC)
- **Self-Optimizing Knowledge Graph**: Scheduled via user crontab on the VM (`src/knowledge_graph/dreaming_engine.py`):
  1. Harvests session traces across the previous 24 hours.
  2. Applies forensic error penalties to evaluate agent trajectory quality.
  3. Executes ACT-R activation decay on memory nodes.
  4. Predicts and attaches associative cross-session semantic edges.
  5. Atomically regenerates the `/dev/shm/` RAM cache.

### 5. ⚡ Compute-Optimized `c2-standard-16` Infrastructure
- Sized by default to **`c2-standard-16`** (16 vCPUs, 64 GB RAM, 3.8 GHz Turbo Intel Xeon) for rapid Go `language_server` AST compilation, sub-second MCP JSON-RPC dispatch, and high-concurrency 16-worker Nginx reverse proxy routing.

### 6. 🚀 1-Click Cleanroom Destroy & Deploy Pipeline
- Automated script (`scripts/deploy_and_verify.sh`): Executes full service teardown, VM software bootstrapping, Nginx configuration, and automated headless Chrome CDP browser verification with live prompt submission.

### 7. 🧰 Community Skills Catalog (`skills/`)
- Includes 8 pre-configured agent skills: `diagram-renderer`, `finops-focus-auditor`, `open-deep-researcher`, `parallel-task-orchestrator`, `playwright-agent-browser`, `six-hats-evaluator`, `universal-solution-architect`, and `universal-task-sync`.

---

## 📌 Project Overview

**Antigravity Web Hub** is an optimized, security-hardened, and production-ready distribution of Google's [Antigravity (AGY)](https://antigravity.google/) web platform tailored for cloud environments. It transforms Antigravity from a desktop-centric CLI and local GUI tool into a persistent, multi-user web-accessible workspace. 

Running on a headless Google Cloud Platform (GCP) Compute-Optimized VM (`c2-standard-16`), the Web Hub serves Antigravity’s Single Page Application (SPA) to remote teams, protected by an Identity-Aware Proxy (IAP) and a GCP Classic HTTPS Load Balancer with Google-managed SSL.

---

## 🏗️ High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          1. Access Layer                               │
│  User Browser ───[ HTTPS / Google SSO ]───► GCP Load Balancer (IAP)     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ h2
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          2. Routing & Orchestration (Nginx)            │
│                 ┌────────────── Nginx :80 / :8080 ────────┐            │
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
│         Vertex AI API                          Native FastMCP Config   │
│   (streamGenerateContent)                      ├── knowledge_graph     │
│                                                ├── autonomy_engine     │
│                                                ├── deep_research       │
│                                                └── google_workspace    │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown:

1. **GCP Classic HTTPS Load Balancer (IAP Protected):**
   Acts as the single public entry-point. Google Identity-Aware Proxy (IAP) handles user authentication and blocks unauthorized requests before they reach the VM.
2. **Nginx Reverse Proxy (`:80 / :8080`):**
   - **Streaming & UI Traffic:** High-performance real-time RPCs (`StreamAgentStateUpdates`, `ListCustomizations`) and Single Page Application assets route to Go `language_server` on port `8081`.
   - **Storage Polyfills:** Injects `window.nativeStorage` and `window.electronNative` into `<head>` to bypass onboarding friction.
   - **Control/API Traffic:** Requests like `GetUserStatus` and `StartCascade` are proxied to `ccpa_mock.py` on port `8083` for dynamic model catalog routing.
3. **Native Go `language_server` (`:8081`):**
   The core binary from Google's Antigravity SDK running in `--standalone` and `--subclient_type=hub` modes. Manages conversations in SQLite databases (`~/.gemini/antigravity/conversations/`) and orchestrates MCP servers.
4. **Python Sidecar `ccpa_mock.py` (`:8083`):**
   - Dynamic injection of custom model configs (`Gemini 3.7 Flash`, `Gemini 3.6 Flash`, `Claude Opus 5`, etc.).
   - Live streaming proxying to Vertex AI via Google Application Default Credentials (ADC).
5. **Standard FastMCP Servers (`mcp_config.json`):**
   - `knowledge_graph` (Python FastMCP): 0ms shared-memory graph search and context hydration.
   - `autonomy_engine` (Python FastMCP): AAAK 3-pass compression and polyphonic retrieval.
   - `deep_research` (Python FastMCP): Claude Opus agentic loop with DuckDuckGo search.
   - `google_workspace` (Node.js): Direct headless integration with Drive, Sheets, Gmail, and Calendar.

---

## 🚀 One-Click Deployment Pipeline

To run a cleanroom destroy $\rightarrow$ deployment $\rightarrow$ automated CDP browser verification in a single command:

```bash
bash scripts/deploy_and_verify.sh
```

---

## 🛠️ Prerequisites

- A Debian 12 VM in GCP (Compute-Optimized `c2-standard-8` recommended).
- Application Default Credentials configured (`gcloud auth application-default login`).
- Antigravity CLI binary installed (`language_server`). The install script downloads it automatically if missing.

---

## 📖 Documentation

- **[SETUP.md](SETUP.md)** — Step-by-step deployment guide & Workspace OAuth setup
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Component diagram and design details
- **[CHANGELOG.md](CHANGELOG.md)** — Release notes and version history
- **[docs/request-flow.md](docs/request-flow.md)** — End-to-end walkthrough of one turn
- **[docs/mcp.md](docs/mcp.md)** — Adding your own MCP tools

---

## 📄 License

MIT — see [LICENSE](LICENSE).
