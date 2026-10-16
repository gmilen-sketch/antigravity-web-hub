# Antigravity Web Hub (v3.7.0 — Gemini 4 Argon GA & Claude 5.5 Edition)

[![Release](https://img.shields.io/badge/Release-v3.7.0--Stable-brightgreen.svg)](CHANGELOG.md)
[![Antigravity Core](https://img.shields.io/badge/Antigravity_Core-v2.24.0_%7C_CLI_v1.4.0-8A2BE2.svg)](https://antigravity.google)
[![Models](https://img.shields.io/badge/Models-Gemini_4_Argon_GA_%7C_Claude_Opus_5.5_%26_Sonnet_5.5_%26_Fable_5-orange.svg)](#1--dynamic-8-model-ga-catalog-routing-srcccpa_mockpy--srcbootstrapjs)
[![Autonomy Engine](https://img.shields.io/badge/Autonomy_Engine-14_Pillars_%7C_20_Skills_%7C_8_FastMCP-blue.svg)](#2--14-pillar-clean-room-autonomy-engine-20-pd-q-skills--5-subagents)
[![Security](https://img.shields.io/badge/Security-IAP_Zero--Trust_%26_Clean--Room_Certified-success.svg)](https://cloud.google.com/iap)

An enterprise-ready, headless Google Cloud VM deployment and clean-room autonomy architecture for **Google Antigravity 2.0 Web (`v2.24.0` Hub + `v1.4.0` CLI)** — featuring **8 GA models** (**Gemini 4 Argon GA**, **Gemini 3.8 / 3.7 / 3.6 / 3.5 Flash**, **Claude Opus 5.5**, **Claude Sonnet 5.5**, and **Claude Fable 5**), **persistent cross-browser multi-model sidebar sessions (`/api/sessions`)**, **14 Clean-Room Autonomy Pillars**, **20 `PD-Q` Skills**, **8 FastMCP Servers**, **3 Lifecycle Hooks**, **5 Custom Subagents**, and **dynamic official CDN binary updates**.

---

## 🌟 What's New in v3.6.x (Gemini 4 Argon GA, Claude 5.5 & Persistent Sidebar Sessions)

### 1. 🎨 Dynamic 8-Model GA Catalog Routing (`src/ccpa_mock.py` & `src/bootstrap.js`)
Switch seamlessly between all **8 General Availability (GA) Google Gemini and Anthropic Claude models** directly from the Antigravity Web UI selector, backed by native `language_server` protobuf enum mapping and Vertex AI Application Default Credentials (ADC):

| UI Model Label | Proto Enum | Vertex AI Model ID | Context / Output Cap | Key Capability & Regional Routing |
| :--- | :---: | :--- | :---: | :--- |
| **`Gemini 4 Argon`** *(Default Flagship GA)* | `354` | `gemini-4-argon` | `1,048,576` / `65,536` | Flagship 1M-context long-horizon reasoning across `global`, `us`, and `eu` mREP with automatic `sanitize_gemini_4_payload()` parameter guard |
| **`Gemini 3.8 Flash`** *(Recommended)* | `352` | `gemini-3.8-flash` | `1,048,576` / `65,536` | Ultra-low-latency multimodal reasoning, agentic coding, and tool dispatch |
| **`Gemini 3.7 Flash`** | `350` | `gemini-3.7-flash` | `1,048,576` / `65,536` | Dynamic thought circulation and multi-file code refactoring |
| **`Gemini 3.6 Flash`** | `348` | `gemini-3.6-flash` | `1,048,576` / `65,536` | General production multimodal workflows and parallel subagent swarms |
| **`Gemini 3.5 Flash Lite`** | `330` | `gemini-3.5-flash-lite` | `1,048,576` / `65,536` | High-throughput extraction, classification, and sub-110ms Mode B routing |
| **`Claude Opus 5.5 (Vertex AI)`** | `290` | `claude-opus-5-5` | `200,000` / `8,192` | Frontier multi-step architectural synthesis and deep reasoning on Vertex AI |
| **`Claude Sonnet 5.5 (Vertex AI)`** | `333` | `claude-sonnet-5-5` | `200,000` / `8,192` | High-precision code generation, debugging, and diff review on Vertex AI |
| **`Claude Fable 5 (Next-Gen)`** | `340` | `claude-fable-5` | `200,000` / `8,192` | Fast, low-latency next-gen subagent execution on Vertex AI |

- **Strict Gemini 4 GA Parameter Sanitizer (`sanitize_gemini_4_payload`)**: Automatically strips legacy `thinkingBudget`, `candidateCount`, `frequencyPenalty`, and `presencePenalty` fields and normalizes `thinkingLevel="MINIMAL"` $\rightarrow$ `"MEDIUM"` before forwarding to Vertex AI so `gemini-4-argon` calls never fail with HTTP `400`.
- **Zero-Key ADC Streaming**: Translates Connect-RPC / gRPC-Web streams to Vertex AI (`streamGenerateContent` & Anthropic `streamRawPredict`) using VM service account / ADC tokens with automatic exponential backoff.

---

### 2. 💾 Persistent Cross-Browser Multi-Model Sidebar Sessions (`v3.5.2+`)
- **Server-Side Session Store (`GET` & `POST /api/sessions` in `src/ccpa_mock.py`)**: Every new conversation created in the browser or via Connect-RPC (`StartCascade` + `SendUserCascadeMessage`) is atomically persisted to `/mnt/data/projects/persistent_ui_sessions.json` with monotonic step-count protection (`len(new_steps) >= len(existing_steps)`).
- **Live Sidebar Hydration (`JetboxSubscribeToState` & `JetboxSubscribeToSummaries` in `src/bootstrap.js`)**: Automatically injects persisted conversation summaries into `appState.sidebarSections[0].conversations` (`enterprise-workspace`) and synchronizes across all open browsers every `2.5s` without requiring local `localStorage` state.
- **Binary-Protobuf UUID Extraction**: Extracts session UUIDs directly from binary `application/connect+proto` frames (`resolvePrewarmedCid`) so clicked sidebar conversations load their full multi-turn history immediately.

---

### 3. 🚀 Antigravity 2.0 Core Engine (`v2.24.0` Hub + `v1.4.0` CLI) & Bare-Metal Scratch Installer (`v3.5.3+`)
- **Dynamic Official Release Auto-Updater (`scripts/install.sh`)**: Queries the public Antigravity 2.0 release API (`https://antigravity-hub-auto-updater-974169037036.us-central1.run.app/releases`) during install/upgrade to resolve the latest verified release (`2.24.0-5780333019398144`) and downloads all 4 official runtime components from `https://storage.googleapis.com/antigravity-public/`:
  1. **`language_server` (`v2.24.0`, `183.9 MB`)**: Go Language Server & embedded `2.24.0` React SPA Web UI (`--subclient_type=hub --override_ide_version="2.24.0" -standalone`) with native `/healthz` readiness checks.
  2. **`webm_encoder` (`v2.24.0`, `17.1 MB`)**: Native Antigravity 2.0 WebM browser recording & replay video encoder (`resources/bin/webm_encoder`).
  3. **`chrome-devtools-mcp` (`v2.24.0`)**: Official built-in Chrome DevTools MCP browser agent runtime & 7 browser debugging skill bundles.
  4. **`antigravity` Standalone CLI (`v1.4.0`, `214.2 MB`)**: Official companion CLI binary installed to `/usr/local/bin/antigravity`.
- **Zero-Config Bare-Metal Scratch Installation**: `scripts/install.sh` auto-discovers `GOOGLE_CLOUD_PROJECT` and `VM_NAME` from the GCE Metadata Server when `.env` is absent, installs all system/Node/Python dependencies (`chromium`, `psmisc`, `ws`, `nginx`), cleans orphaned processes, and verifies readiness across `/healthz`, `/api/version`, and `/` (`id="root"`).

---

### 4. 🛡️ 14-Pillar Clean-Room Autonomy Engine, 20 `PD-Q` Skills & 5 Subagents
- **3 Deterministic Lifecycle Hooks (`src/hooks/` & `hooks.json`)**:
  1. **`PreInvocation` (`kg_pre_invocation_hook.py` `v3.5`)**: Sub-millisecond `/dev/shm/kg_warm_cache.json` entity grounding, pure-Python Porter stemmer, `0.05`-grid confidence quantization, 2-hop neighborhood expansion, and Top-3 `okf:*` dossier co-bundling.
  2. **`PreToolUse` (`sentinel_dispatch.py` `v2.0`)**: Modular security and governance rules (`r31_hook_integrity_guard.py`, `destructive_commands.py`, `deprecated_models.py`, `file_bounds.py`, `rule_11_anonymization.py`, `zero_latex.py`).
  3. **`Stop` (`agent_stop_black_hat_gate.py` `v4.8`)**: 2-Stage Stateless Goldfish $\rightarrow$ Isolated Judge completion gate enforcing `C1–C11` forensic contracts, `C9` Pre-Prose Table Readback Gate, Bottom-Up `### ⚡ TL;DR` validation, and Git Diff Anti-Test-Tampering checks.
- **P0 (`CB-1..CB-8`) & P1 (`P1-CB-1..P1-CB-8`) Quality-First Engines (`src/autonomy_engine/`)**: Bernstein disjoint write-set verification (`CB-8`), 4-tier rule precedence, Prompt-Injection Context Firewall (`P1-CB-8` PICC), and strict primary-source abstention.
- **6-Field BM25F + Hybrid Graph-RAG Polyphonic Retriever (`polyphonic_retriever.py` `v2.0`)**: Combines 6-field weighted BM25F lexical scoring with 1-hop/2-hop Knowledge Graph structural proximity boost and line-numbered chunking over `kb/` (`OKF v0.2`).
- **Bayesian Self-Grill Prior Engine (`grill_me_prior_engine.py` `v2.5`), Six Thinking Hats Delphi Router (`delphi_six_hats_task_router.py`), 5-Check Web UI Geometry Auditor (`audit_web_ui_geometry.py` `v2.0`), & 14-Mode Unified Evaluation Router (`unified_eval_router.py` `v2.5`)**.
- **5 Custom Subagents (`agents/`)**: `black-hat-goldfish` (Stage-1 Stateless Forensic Investigator), `black-hat-judge` (Stage-2 Isolated Adjudicator), `black-hat-critic`, `dreaming-improvement-reasoner`, and `workspace-housekeeper`.
- **20 Clean-Room `PD-Q` Skills (`skills/manifest.json`)**: `antigravity-web-builder`, `black-hat-analysis`, `diagram-renderer`, `finops-focus-auditor`, `first-principles-brainstormer`, `golden-ab-testing`, `idea-evaluator`, `issue-tracker-manager`, `migration-center-architect`, `open-deep-researcher`, `p0-quality-first-engine`, `p1-quality-first-engine`, `parallel-task-orchestrator`, `playwright-agent-browser`, `self-grill`, `six-hats-evaluator`, `universal-solution-architect`, `universal-task-sync`, `workspace-docs-publisher`, and `workspace-slides-generator`.

---

### 5. 🔌 8 Standard FastMCP Servers (`mcp_config.json`)
All auxiliary agent capabilities run as standard **Model Context Protocol (MCP)** servers over STDIO JSON-RPC (`transport="stdio"`):
1. **`knowledge_graph`** (`src/knowledge_graph/kg_mcp_server.py`): Bitemporal SQLite-WAL graph search, concept upsertion, 2-hop traversal, and `/dev/shm` warm cache hydration.
2. **`autonomy_engine`** (`src/autonomy_engine/mcp_autonomy_hub.py`): AAAK 3-pass lossless compression, 6-field BM25F + Graph-RAG retrieval, P0/P1 circuit-breakers, and 14-mode evaluation routing.
3. **`diagram_renderer`** (`src/diagram_renderer/diagram_mcp_server.py`): BENTO `v15.5` orthogonal SVG compiler with $r=5.5\,\text{px}$ rounded Manhattan connectors and Mermaid rendering.
4. **`browser_cdp`** (`src/mcp_servers/browser_cdp_mcp.py`): Headless Chromium CDP (`:9222`) automation, 5-check DOM/SVG geometry auditing, and Shadow-DOM inspection.
5. **`cloud_telemetry`** (`src/mcp_servers/cloud_telemetry_mcp.py`): Cloud Monitoring P99 latency SLAs and BigQuery FOCUS billing / CUD commitment audits.
6. **`workspace_docs`** (`src/mcp_servers/workspace_docs_mcp.py`): 3-Tab Inverted-Pyramid (`AGENT-SSOT-v1`) docs formatter, 4-card Cloudstyle slide builder, and 1-Sheet 3-Row Staging Diff generator.
7. **`deep_research`** (`src/mcp_deep_research.py`): Multi-turn agentic deep research loop with live DuckDuckGo web search and citation synthesis.
8. **`google_workspace`** (`src/mcp_google_workspace/index.js`): Headless operations across Gmail, Google Calendar, Google Drive, and Google Sheets.

---

## 🏗️ High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                               1. Access Layer                                    │
│   User Browser ───[ HTTPS / Google Cloud IAP SSO ]───► GCP Load Balancer (:443)  │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │ HTTP/2
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        2. Routing & Orchestration (Nginx :8080)                  │
│          ┌─────────────────────────── Nginx :8080 ────────────────────────┐      │
│          │                                                                │      │
│  /GetUserStatus, /StartCascade,                         Streaming RPCs &  │      │
│  /api/sessions, /api/autonomy, /api/version             Static Web Assets │      │
│          ▼                                                                ▼      │
│   ccpa_mock.py (:8083)                                   language_server (:8081) │
│   (8-Model Router, Session Store & Autonomy Gateway)     (Antigravity 2.24.0 Go) │
└──────────┬────────────────────────────────────────────────────────────────┬──────┘
           │                                                                │
┌──────────┼────────────────────────────────────────────────────────────────┼──────┐
│          │             3. Models, Memory & 8 FastMCP Servers              │      │
│          ▼                                                                ▼      │
│   Vertex AI API (ADC Bearer)                                Native FastMCP STDIO │
│   ├── Gemini 4 Argon (354, 1M GA)                           ├── knowledge_graph  │
│   ├── Gemini 3.8 / 3.7 / 3.6 / 3.5 Flash                    ├── autonomy_engine  │
│   ├── Claude Opus 5.5 (290)                                 ├── diagram_renderer │
│   ├── Claude Sonnet 5.5 (333)                               ├── browser_cdp      │
│   └── Claude Fable 5 (340)                                  ├── cloud_telemetry  │
│                                                             ├── workspace_docs   │
│                                                             ├── deep_research    │
│                                                             └── google_workspace │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start & Verification

### 1. One-Command Bare-Metal Install (On Any Debian 12 / Ubuntu GCE VM)
```bash
sudo bash scripts/install.sh
```
`scripts/install.sh` auto-discovers your GCP project and VM name from the GCE Metadata Server, downloads the latest Antigravity `2.24.0` Core + `1.4.0` CLI binaries from the official public CDN, installs all 20 skills, 8 FastMCP servers, and 3 lifecycle hooks, starts `antigravity-web.service` + `nginx`, and verifies `/healthz` and `/api/version`.

### 2. Full Clean-Room Unit & Integration Test Suite (`27/27` Tests)
```bash
python3 -B tests/test_autonomy_kg_hooks.py -v
python3 -B src/hooks/black_hat_analyzer.py --target .
```

### 3. Headless Chromium CDP End-to-End Verification (`scripts/verify_e2e.js`)
```bash
LB_IP="127.0.0.1:8080" E2E_SCREENSHOT_PATH="/tmp/antigravity_e2e_verified.png" node scripts/verify_e2e.js
```

---

## 📖 Documentation

- **[SETUP.md](SETUP.md)** — Step-by-step Terraform, workstation, and manual VM deployment guide & IAP OAuth setup
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Component topology, binary manifest, and Connect-RPC / gRPC-Web routing details
- **[CHANGELOG.md](CHANGELOG.md)** — Release notes and version history (`v2.1.0` $\rightarrow$ `v3.7.0`)
- **[docs/request-flow.md](docs/request-flow.md)** — Byte-level walkthrough of a multi-model turn (`Gemini 4 Argon` & `Claude Opus 5.5`)
- **[docs/mcp.md](docs/mcp.md)** — Guide to the 8 built-in FastMCP servers and adding custom MCP tools

---

## 📄 License

MIT — see [LICENSE](LICENSE).
