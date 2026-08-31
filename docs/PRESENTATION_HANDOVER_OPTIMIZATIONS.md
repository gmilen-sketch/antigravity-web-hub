# 🚀 Google Antigravity Web: Architecture, Optimizations & Presentation Handover

**Version:** 3.1.1 (Production & Clean-Room Verified)  
**Author:** Milen Genchev (`mgenchev@google.com`)  
**Target Audience:** Cloud Engineers, Technical Architects, Customer Engineering Leadership, Open-Source Community  
**Date:** August 2026  

---

## 🎯 Executive Summary & Presentation Narrative

### The Vision
Google Antigravity (AGY) is Google's next-generation AI coding platform and Mission Control IDE. While originally architected as a desktop-centric electron application and local CLI, **Antigravity Web Hub** transforms it into an **enterprise-ready, multi-user, cloud-native Web IDE** accessible directly through standard web browsers, protected by Identity-Aware Proxy (IAP) and backed by scalable Google Cloud infrastructure.

### The Engineering Challenge
Running a desktop Electron IDE natively in the cloud revealed major architectural friction points:
1. **Desktop Host Security Gates**: Upstream Go Language Server strictly rejected any non-localhost HTTP Host headers with `401 Unauthorized`.
2. **Protocol & Routing Incompatibilities**: Browser Connect-RPC/gRPC-Web framing collided with Vertex AI streaming endpoints and triggered CORS preflight rejections.
3. **Onboarding & React State Deadlocks**: Desktop onboarding state machines caused blank white screens (`<div id="root"></div>`) without local Electron IPC storage.
4. **Dynamic Model Routing & Marketplace Entitlements**: Need for seamless switching between Gemini 3.7/3.6 and Anthropic Claude models without crashing when specific project marketplace licenses were absent.
5. **Render Latency & Cold Starts**: Standard compute VMs caused high Time-To-Initial-Render (TTIR > 6.8s) during AST indexing and Monaco editor mounting.

---

## 📊 Presentation Structure & High-Level Outline

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             ANTIGRAVITY WEB HUB ARCHITECTURE                             │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
┌───────────────────┐             ┌───────────────────┐             ┌───────────────────┐
│ 1. ACCESS & EDGE  │             │  2. CORE ROUTING  │             │ 3. INTELLIGENCE   │
│ • GCP Classic LB  │             │ • Nginx Decoupler │             │ • Vertex AI Multi-│
│ • IAP Zero-Trust  │ ──(HTTPS)──►│ • Go Server (:8081│ ──(Stream)─►│   Model Gateway   │
│ • Host Rewriting  │             │ • Python CCPA     │             │ • FastMCP Servers │
│ • CORS Stripping  │             │   Sidecar (:8083) │             │ • Knowledge Graph │
└───────────────────┘             └───────────────────┘             └───────────────────┘
         │                                 │                                 │
         └─────────────────────────────────┼─────────────────────────────────┘
                                           ▼
                          ┌─────────────────────────────────┐
                          │ 4. RUNTIME & INFRASTRUCTURE     │
                          │ • c2-standard-16 Compute Tier   │
                          │ • Storage & Electron Polyfills  │
                          │ • Automated Cleanroom Pipeline  │
                          │ • 23:50 UTC Dreaming Engine     │
                          └─────────────────────────────────┘
```

---

## 🏛️ Deep-Dive Pillar Breakdown (Slide-by-Slide Guide)

### Pillar 1: Ingress, Reverse Proxy & Network Hardening

* **The Problem**:
  * Upstream Go `language_server` enforces strict local binding. Any external request passing domain or IP host headers is rejected with `401 Unauthorized Host (Localhost only)`.
  * Upstream server emitting duplicate CORS headers caused Chrome to block responses with `Multiple CORS header not allowed`.
  * Browser preflights (`OPTIONS`) were unhandled or dropped.
* **The Solution**:
  * **Host Rewriting**: Nginx reverse proxy forcefully rewrites `proxy_set_header Host "127.0.0.1:8081";` on all upstream proxy passes.
  * **Duplicate Header Elimination**: Added `proxy_hide_header Access-Control-Allow-Origin;` and `proxy_hide_header Access-Control-Allow-Credentials;` in Nginx, allowing Nginx to be the sole authority for CORS.
  * **Native Preflight Responder**: Configured native HTTP 204 preflight handler for custom headers (`x-grpc-web`, `x-codeium-csrf-token`).
  * **Zero-Trust Security**: Fronted by GCP Classic HTTPS Load Balancer with Identity-Aware Proxy (IAP) and Google-managed SSL (`nip.io`), leaving 0 open public ingress ports on the VM.

---

### Pillar 2: Dual-Port Routing & Protocol Decoupling

* **The Problem**:
  * Monolithic Go Language Server cannot be easily modified at runtime to inject custom Vertex AI models or dynamic cloud translation layers.
* **The Solution**:
  * **Split-Port Architecture**:
    * **Port `8081` (Native Go `language_server`)**: Serves React SPA bundles, Monaco editor, file trees, terminal streaming, and internal Connect-RPC state.
    * **Port `8083` (Python `ccpa_mock.py` Sidecar)**: Intercepts specialized LLM & trajectory routing endpoints:
      * `/exa.language_server_pb.LanguageServerService/StartCascade`
      * `/exa.language_server_pb.LanguageServerService/SendUserCascadeMessage`
      * `/exa.language_server_pb.LanguageServerService/StreamAgentStateUpdates`
      * `/exa.language_server_pb.LanguageServerService/UpdateConversationAnnotations`
      * `/exa.language_server_pb.LanguageServerService/GetUserStatus`
      * `/exa.language_server_pb.LanguageServerService/GetAuthStatus`
  * **Binary Frame Marshalling**: Sidecar converts incoming gRPC-Web binary frames (`\x00` length prefix + JSON payload + `\x80` trailer frame) into Vertex AI SSE streaming candidates and returns native Connect streams.

---

### Pillar 3: Dynamic Multi-Model Catalog & Resilient Routing

* **The Problem**:
  * Default Antigravity UI hardcodes a single model family.
  * Model switching suffered from a React re-render bug where `defaultOverrideModelConfig` continuously reverted user selection back to Gemini on every click.
  * Attempting to call Anthropic Claude on GCP projects without marketplace enablement crashed the conversation with HTTP 404.
* **The Solution**:
  * **Multi-Model Catalog**: Exposed 6 canonical production models in the dropdown:
    1. **Gemini 3.7 Flash** (`MODEL_GOOGLE_GEMINI_RIFTRUNNER_THINKING_LOW`, *Recommended Default*)
    2. **Gemini 3.6 Flash** (`MODEL_GOOGLE_GEMINI_2_5_FLASH`, *General Production*)
    3. **Gemini 3.5 Flash Lite** (`MODEL_GOOGLE_GEMINI_2_5_FLASH_LITE`, *High Throughput*)
    4. **Claude 3.7 Sonnet** (`MODEL_ANTHROPIC_CLAUDE_3_5_SONNET`, *Complex Reasoning*)
    5. **Claude Opus 5** (`MODEL_ANTHROPIC_CLAUDE_OPUS_4_5`, *Deep Reasoning*)
    6. **Claude Fable 5** (`MODEL_ANTHROPIC_CLAUDE_3_5_HAIKU`, *Low-Latency Partner*)
  * **Model Lock-In Fix**: Omitted `defaultOverrideModelConfig` from configuration payloads and injected client DOM click listeners in `bootstrap.js` with `localStorage` persistence, ensuring model selections persist across turns.
  * **Anthropic 404 Automatic Failover**: Integrated exception handling in `src/ccpa_mock.py` that intercepts Anthropic marketplace 404s and **seamlessly falls back to `gemini-3.7-flash`**, continuing token streaming without throwing broken pipe errors.

---

### Pillar 4: Zero-Friction Web Bootstrapping & Storage Polyfills

* **The Problem**:
  * Desktop compiled SPA expects Electron runtime (`window.nativeStorage`, `window.electronNative`). Without them, the page crashes or redirects indefinitely to onboarding screens.
  * React root evaluated `initialized === false` when `JetboxSubscribeToState` was pending, causing a blank white screen (`<div id="root"></div>`).
* **The Solution**:
  * **Injected Storage Bridge**: Injected polyfills for `window.nativeStorage` (backed by browser `localStorage`) and `window.electronNative` via Nginx `<head>` `sub_filter`.
  * **White Screen Fix**: Streamed an immediate initial gRPC-web state frame (`{ appState: { agentOnboardingCompleted: 2 }, userConfig: {} }`) over `ReadableStream` on connection, immediately toggling `initialized: true` in React.
  * **Auth & NUX Bypass**: Automatically pre-configured `jetski_state.pbtxt` with completed onboarding steps (`MANAGER_WELCOME`, `USAGE_MODE`, `AGENT_CONFIGURATION`, `ADD_WORKSPACE`) and 23 seen NUX flags.

---

### Pillar 5: Compute Sizing & Performance Benchmarks

* **The Infrastructure Upgrade**:
  * Migrated from baseline `c2-standard-8` (8 vCPU / 32 GB) to **`c2-standard-16`** (16 vCPUs, 64 GB RAM, 3.8 GHz Turbo Intel Xeon).
* **The Empirical Benchmark Results**:
  * **Time-to-Initial-Render (TTIR)**: Dropped by **41.6%** (from 6.80s down to **3.97s**).
  * **Language Server AST Indexing**: Real-time Go compilation and indexing without CPU throttling.
  * **Nginx Worker Concurrency**: Scaled to 16 worker processes to support high-throughput parallel gRPC streaming channels.

---

### Pillar 6: Knowledge Graph Memory, FastMCP & Autonomy Suite

* **Long-Term Property Graph**:
  * Bitemporal graph stored at `~/.gemini/antigravity/knowledge_graph.json` with SQLite write-ahead logging (WAL).
* **0ms Shared-Memory RAM Cache**:
  * Atomic shared-memory pre-warmed cache at `/dev/shm/kg_warm_cache.json` enabling sub-millisecond graph retrieval during prompt compilation.
* **Automated Nightly Dreaming Engine (23:50 UTC)**:
  * User crontab runs `dreaming_engine.py` nightly:
    1. Harvests session traces across the prior 24 hours.
    2. Applies forensic error penalties and classifies failure modes.
    3. Runs ACT-R activation decay on memory nodes.
    4. Predicts associative cross-session semantic edges.
    5. Re-warms `/dev/shm/` cache.
* **Standard Model Context Protocol (MCP)**:
  * Refactored all auxiliary tooling into standard STDIO JSON-RPC FastMCP modules (`knowledge_graph`, `autonomy_engine`, `deep_research`, `google_workspace`).

---

### Pillar 7: Standalone Packaging & Automated Verification Pipeline

* **Standalone Binary Bundling**:
  * Discovered that downloading `language_server_linux_x64` from Google CDN provided the extension client (lacking `--subclient_type=hub` flags).
  * Bundled the official standalone Go `language_server` binary in `bin/` and updated `scripts/install.sh` to prioritize local assets.
* **1-Click Clean-Room Pipeline (`scripts/deploy_and_verify.sh`)**:
  * Packages clean repository $\rightarrow$ Uploads via IAP $\rightarrow$ Executes clean teardown & install $\rightarrow$ Configures Nginx & Systemd $\rightarrow$ Runs automated Chrome CDP verification suite.
* **Persistent Stream In-Browser Verification**:
  * Configured `verify_e2e.js` and `gbrowser` with `waitUntil: "none"` to accommodate long-lived persistent chunked streams (`JetboxSubscribeToSummaries`, `JetboxSubscribeToState`, `ProjectUpdatesStream`).

---

## 🎤 Presentation Delivery Scripts & Talking Points

### Option A: 5-Minute Executive / Lightning Talk
* **Slide 1 (Problem)**: "Antigravity is amazing on desktop, but enterprise teams need cloud accessibility, centralized compliance, and zero local setup."
* **Slide 2 (Architecture)**: "We built a dual-port decoupled architecture: Nginx handles ingress and Electron polyfills, Go serves the SPA, and a Python sidecar routes to Vertex AI."
* **Slide 3 (Key Breakthroughs)**: "We solved the 401 Host header gate, eliminated CORS bugs, bypassed onboarding white-screens, and added 6 dynamic models with auto-failover."
* **Slide 4 (Performance & Impact)**: "Upgrading to C2-16 cut initial render latency by 41.6% to 3.9s. Full clean-room deployments are 100% automated in 1 command."

### Option B: 15-Minute Technical Deep-Dive
1. **Introduction & Motivation** (2 mins)
2. **Reverse Proxy & Host Rewriting Forensics** (3 mins)
3. **Dual-Port gRPC-Web Streaming & Vertex AI Translation** (3 mins)
4. **Electron Storage Polyfills & React Initialization Fix** (3 mins)
5. **Knowledge Graph, FastMCP & 23:50 UTC Dreaming Engine** (2 mins)
6. **E2E Clean-Room Automated Testing & Live Demo** (2 mins)

---

## 📋 Key Files & Repositories Reference

* **Core GitHub Repositories**:
  * `git@github.com:gmilen-sketch/antigravity-web-hub.git` (`main`)
  * `git@github.com:cloud-gtm/antigravity-web-hub.git` (`main`, `release/v3.1.0`, `feat/v3.1.0-release-multimodel-mcp`)
* **Key Implementation Files**:
  * `src/ccpa_mock.py`: Python Vertex AI / Claude routing sidecar & gRPC-Web framing.
  * `config/nginx.conf`: Nginx reverse proxy, Host rewriting, CORS rules, and polyfill injection.
  * `scripts/install.sh`: Host bootstrap, binary placement, FastMCP config, and systemd service.
  * `scripts/deploy_and_verify.sh`: 1-click clean-room deploy and CDP verification runner.
  * `scripts/gcp_destroy.sh`: 8-step GCP infrastructure teardown script.
  * `scripts/gcp_setup_vm.sh`: Sized C2-standard-16 VM provisioner with Argolis VPC/NAT compliance.
  * `scripts/gcp_setup_lb.sh`: Classic HTTPS Load Balancer, SSL cert, and IAP setup.
  * `CHANGELOG.md`: Complete chronological release history (v2.1.0 $\rightarrow$ v3.1.1).
