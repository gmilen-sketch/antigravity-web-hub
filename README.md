# Antigravity Web Hub (v3.9.0 — Antigravity Core 2.29.1 + CLI 1.5.3, 4-Hook Adaptive Governance & Clean-Room Certified Edition)

[![Release](https://img.shields.io/badge/Release-v3.9.0--Stable-brightgreen.svg)](CHANGELOG.md)
[![Antigravity Core](https://img.shields.io/badge/Antigravity_Core-v2.29.1_%7C_CLI_v1.5.3-8A2BE2.svg)](https://antigravity.google)
[![Models](https://img.shields.io/badge/Models-Gemini_4_Argon_GA_%7C_Claude_Opus_5.5_%26_Sonnet_5.5_%26_Fable_5-orange.svg)](#1--dynamic-8-model-ga-catalog-routing-srcccpa_mockpy--srcbootstrapjs)
[![Autonomy Engine](https://img.shields.io/badge/Autonomy_Engine-14_Pillars_%7C_20_Skills_%7C_8_FastMCP-blue.svg)](#2--14-pillar-clean-room-autonomy-engine-20-pd-q-skills--5-subagents)
[![Security](https://img.shields.io/badge/Security-IAP_Zero--Trust_%26_Clean--Room_Certified-success.svg)](https://cloud.google.com/iap)

An enterprise-ready, headless Google Cloud VM deployment and clean-room autonomy architecture for **Google Antigravity 2.0 Web (`v2.29.1` Hub + `v1.5.3` CLI)** — featuring **8 GA models** (**Gemini 4 Argon GA**, **Gemini 3.8 Flash**, **Gemini 3.5 Flash**, **Gemini 3.6 / 3.5 Flash**, **Claude Opus 5.5**, **Claude Sonnet 5.5**, and **Claude Fable 5**), **persistent cross-browser multi-model sidebar sessions (`/api/sessions`)**, **Foundational Reference Knowledge Graph (`18` nodes / `32` edges covering Web Hub self-docs, Gemini models, Google ADK, `agents-cli`, and 5 `OKF v0.2` `kb/` dossiers) with `/dev/shm/agw_kg_warm_cache.json` namespace isolation**, **14 Wave-12 Clean-Room Kernels (`AGW-W12-01`..`14`)**, **Turnkey Paired A/B Benchmark Runner (`scripts/run_ab_benchmark.py`)**, **14 Clean-Room Autonomy Pillars**, **20 `PD-Q` Skills**, **8 FastMCP Servers**, **4 Lifecycle Hooks (`PreInvocation`, `PostInvocation`, `PreToolUse`, `Stop`)**, **5 Custom Subagents**, and **dynamic official CDN binary updates**.

---

## 🌟 What's New in v3.9.0 (Core 2.29.1 + CLI 1.5.3, 100% Zero-Mock Native `:8081` Execution, Adaptive `v4.18` Goldfish Wave & `force_ask` Security)

- **100% Zero-Mock Native `:8081` Execution, Headless OAuth Seeding & Bidirectional Anthropic/Gemini Tool Translation (`src/bootstrap.js`, `src/ccpa_mock.py`, `src/mcp_servers/cloud_telemetry_mcp.py`, `config/nginx.conf`)**: Purged all browser-side cascade fetch overrides and synthetic telemetry footers (`src/bootstrap.js` shrunk to `390` lines of pure Electron/storage polyfills + 8-model selector sync); added `--seed-oauth-token` (`/oauth-token-callback` on `127.0.0.1:8081`) for unattended headless VM authentication; mapped gateway executor placeholders (`MODEL_PLACEHOLDER_M36`/`M18`/`M50`) to the active UI model; implemented bidirectional Anthropic `tools`/`tool_use`/`tool_result` $\leftrightarrow$ Gemini `functionDeclarations`/`functionCall`/`functionResponse` SSE streaming translation + `normalize_gemini_tool_calls()` `call_mcp_tool` `Arguments` unwrapping; and added eager BigQuery `discover_billing_export_tables` & `query_bigquery_billing` tools (`40/40` unit tests passing).
- **Foundational Self-Documentation, Gemini Model, ADK & CLI Knowledge Graph (`src/knowledge_graph/init_knowledge_graph.py` & `kb/`)**: Fresh installs initialize `knowledge_graph.json` with **18 clean-room reference nodes and 32 topological edges** (`doc:antigravity_web_hub`, `doc:antigravity_cli_sdk`, `doc:google_adk`, `doc:agents_cli`, `doc:gemini_vertex_models`, `doc:autonomy_hooks_and_skills`, `model:gemini_4_argon`, `model:gemini_3_8_flash`, `model:gemini_3_5_flash`, `model:gemini_3_6_flash`, `model:gemini_3_5_flash_lite`, `mcp:knowledge_graph`, `mcp:autonomy_engine`, plus all **5 `OKF v0.2` `kb/` reference dossiers**) and isolate the shared-memory warm cache at `/dev/shm/agw_kg_warm_cache.json` (`KG_WARM_CACHE_PATH`). Pass `--empty` (`AGW_EMPTY_KG=1`) for a zero-node graph in null-control A/B benchmarks.
- **14 Graduated Wave-12 Clean-Room Kernels (`AGW-W12-01`..`AGW-W12-14`)**: Dual-Mode Execution Classifier (`SWE_BENCHMARK_MODE` vs `PORTFOLIO_MODE`), Turn-0 Frozen KV-Cache Kernel Guard, Strict `PreInvocation` Schema Sanitizer, Single-Pass Current-Turn Transcript Inspector, Inline `python3 -c` Heredoc Auto-Rewriter, Multi-Tenant Sandbox & Own-CID Isolation Guard, Reactive Wakeup Anti-Polling Circuit Breaker, Zero-`.pyc` In-Memory AST Validator, Sub-Millisecond IDF Token Index, Non-Compounding Temporal Decay (`base_confidence`) + 7-Day Patch TTL Guard, Polyphonic Conversational Query Rewriter & Identity Headers, Multi-Step Cascade True-Completion Barrier (`T3-8`), Post-Mutation Local Test Proof Gate, and Non-Interactive VCS Flag Enforcer.
- **Turnkey Paired Harness A/B Benchmark Orchestrator (`scripts/run_ab_benchmark.py`)**: Evaluates Vanilla Antigravity (Arm A, `:9080`) vs Customized Antigravity (Arm B, `:9081`) under strict ceteris-paribus controls (`python3 -B scripts/run_ab_benchmark.py --self-test`, `--mode dual-daemon`, `--mode harbor`) with Gate G15 Reference/Null validation, Hake's Normalized Gain $g$, exact McNemar $p$-value, and `pass@k` / `pass^k`.

### 1. 🎨 Dynamic 8-Model GA Catalog Routing (`src/ccpa_mock.py` & `src/bootstrap.js`)
Switch seamlessly between all **8 General Availability (GA) Google Gemini and Anthropic Claude models** directly from the Antigravity Web UI selector, backed by native `language_server` protobuf enum mapping and Vertex AI Application Default Credentials (ADC):

| UI Model Label | Proto Enum | Vertex AI Model ID | Context / Output Cap | Key Capability & Regional Routing |
| :--- | :---: | :--- | :---: | :--- |
| **`Gemini 4 Argon`** *(Default Flagship GA)* | `354` | `gemini-4-argon` | `1,048,576` / `131,072` | Flagship 1M-context long-horizon reasoning across `global`, `us`, and `eu` mREP with automatic `sanitize_gemini_4_payload()` parameter guard |
| **`Gemini 3.8 Flash`** *(Recommended)* | `352` | `gemini-3.8-flash` | `1,048,576` / `131,072` | Ultra-low-latency multimodal reasoning, agentic coding, and tool dispatch |
| **`Gemini 3.6 Flash`** | `348` | `gemini-3.6-flash` | `1,048,576` / `131,072` | General production multimodal workflows and parallel subagent swarms |
| **`Gemini 3.5 Flash`** *(GA EU Residency)* | `350` | `gemini-3.5-flash` | `1,048,576` / `65,535` | Long-GA production & EU regional data-residency text synthesis |
| **`Gemini 3.5 Flash Lite`** | `330` | `gemini-3.5-flash-lite` | `1,048,576` / `65,536` | High-throughput extraction, classification, and sub-110ms Mode B routing |
| **`Claude Opus 5.5 (Vertex AI)`** | `290` | `claude-opus-5-5` | `200,000` / `16,384` | Frontier multi-step architectural synthesis and deep reasoning on Vertex AI |
| **`Claude Sonnet 5.5 (Vertex AI)`** | `333` | `claude-sonnet-5-5` | `200,000` / `16,384` | High-precision code generation, debugging, and diff review on Vertex AI |
| **`Claude Fable 5 (Next-Gen)`** | `340` | `claude-fable-5` | `200,000` / `16,384` | Fast, low-latency next-gen subagent execution on Vertex AI |

- **Strict Gemini 4 GA Parameter Sanitizer (`sanitize_gemini_4_payload`)**: Automatically strips legacy `thinkingBudget`, `candidateCount`, `frequencyPenalty`, and `presencePenalty` fields and normalizes `thinkingLevel="MINIMAL"` $\rightarrow$ `"MEDIUM"` before forwarding to Vertex AI so `gemini-4-argon` calls never fail with HTTP `400`.
- **Zero-Key ADC Streaming**: Translates Connect-RPC / gRPC-Web streams to Vertex AI (`streamGenerateContent` & Anthropic `streamRawPredict`) using VM service account / ADC tokens with automatic exponential backoff.

---

### 2. 💾 Persistent Cross-Browser Multi-Model Sidebar Sessions (`v3.5.2+`)
- **Server-Side Session Store (`GET` & `POST /api/sessions` in `src/ccpa_mock.py`)**: Every new conversation created in the browser or via Connect-RPC (`StartCascade` + `SendUserCascadeMessage`) is atomically persisted to `/mnt/data/projects/persistent_ui_sessions.json` with monotonic step-count protection (`len(new_steps) >= len(existing_steps)`).
- **Live Sidebar Hydration (`JetboxSubscribeToState` & `JetboxSubscribeToSummaries` in `src/bootstrap.js`)**: Automatically injects persisted conversation summaries into `appState.sidebarSections[0].conversations` (`enterprise-workspace`) and synchronizes across all open browsers every `2.5s` without requiring local `localStorage` state.
- **Binary-Protobuf UUID Extraction**: Extracts session UUIDs directly from binary `application/connect+proto` frames (`resolvePrewarmedCid`) so clicked sidebar conversations load their full multi-turn history immediately.

---

### 3. 🚀 Antigravity 2.0 Core Engine (`v2.29.1` Hub + `v1.5.3` CLI) & Bare-Metal Scratch Installer (`v3.5.3+`)
- **Dynamic Official Release Auto-Updater (`scripts/install.sh`)**: Queries the public Antigravity 2.0 release API (`https://antigravity-hub-auto-updater-974169037036.us-central1.run.app/releases`) during install/upgrade to resolve the latest verified release (`2.29.1-5241471524274176`) and downloads all 4 official runtime components from `https://storage.googleapis.com/antigravity-public/`:
  1. **`language_server` (`v2.29.1`, `183.9 MB`)**: Go Language Server & embedded `2.29.1` React SPA Web UI (`--subclient_type=hub --override_ide_version="2.24.0" -standalone`) with native `/healthz` readiness checks.
  2. **`webm_encoder` (`v2.29.1`, `17.1 MB`)**: Native Antigravity 2.0 WebM browser recording & replay video encoder (`resources/bin/webm_encoder`).
  3. **`chrome-devtools-mcp` (`v2.29.1`)**: Official built-in Chrome DevTools MCP browser agent runtime & 7 browser debugging skill bundles.
  4. **`antigravity` Standalone CLI (`v1.5.3`, `214.2 MB`)**: Official companion CLI binary installed to `/usr/local/bin/antigravity`.
- **Zero-Config Bare-Metal Scratch Installation**: `scripts/install.sh` auto-discovers `GOOGLE_CLOUD_PROJECT` and `VM_NAME` from the GCE Metadata Server when `.env` is absent, installs all system/Node/Python dependencies (`chromium`, `psmisc`, `ws`, `nginx`), cleans orphaned processes, and verifies readiness across `/healthz`, `/api/version`, and `/` (`id="root"`).

---

### 4. 🛡️ 14-Pillar Clean-Room Autonomy Engine, 20 `PD-Q` Skills & 5 Subagents
- **4 Deterministic Lifecycle Hooks (`src/hooks/`, `run_hook_safe.sh` & `hooks.json` + Subagent `agents/*/hooks.json`)**:
  1. **`PreInvocation` (`kg_pre_invocation_hook.py` `v3.9.0`)**: Sub-millisecond `/dev/shm/agw_kg_warm_cache.json` + `/dev/shm/agw_turn_cache_<cid>.json` grounding, `HookSystemMessage` schema, `/dev/shm/<dir>` SWE workspace router (`min_stop_seconds: 3`), XDG noise stripping, and `[1/2]` option carryover.
  2. **`PostInvocation` (`black_hat_in_progress_ux_hook.py` `v4.17`)**: Zero-LLM-token `[!WARNING]` verification progress banner and `<artifact>.metadata.json` `userFacing` card holdback during Goldfish/Judge execution.
  3. **`PreToolUse` (`sentinel_dispatch.py` `v3.9.0`)**: Modular security and governance rules (`force_ask` `r31_hook_integrity_guard.py` & `destructive_commands.py`, `deprecated_models.py`, `S-01` `_FILE_SCHEMA_TOOLS` scoping, `GOLDFISH-RO-1` read-only sandbox, and `L3` identical-command anti-spin).
  4. **`Stop` (`agent_stop_black_hat_gate.py` `v4.18`)**: Adaptive `K=1..3` `[SHARD:<id>]` Multi-Goldfish $\rightarrow$ Holistic Judge completion gate with selective shard delta retry, `C6-Multi`/`C6-Holistic` union + seam checks, `C9` `>=5`-row table readback, and atomic artifact card restoration.
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
│   (8-Model Router, Session Store & Autonomy Gateway)     (Antigravity 2.29.1 Go) │
└──────────┬────────────────────────────────────────────────────────────────┬──────┘
           │                                                                │
┌──────────┼────────────────────────────────────────────────────────────────┼──────┐
│          │             3. Models, Memory & 8 FastMCP Servers              │      │
│          ▼                                                                ▼      │
│   Vertex AI API (ADC Bearer)                                Native FastMCP STDIO │
│   ├── Gemini 4 Argon (354, 1M GA)                           ├── knowledge_graph  │
│   ├── Gemini 4 / 3.8 / 3.6 / 3.5 / Lite                      ├── autonomy_engine  │
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
`scripts/install.sh` auto-discovers your GCP project and VM name from the GCE Metadata Server, downloads the latest Antigravity `2.29.1` Core + `1.5.3` CLI binaries from the official public CDN, installs all 20 skills, 8 FastMCP servers, and 4 lifecycle hooks, starts `antigravity-web.service` + `nginx`, and verifies `/healthz` and `/api/version`.

### 2. Full Clean-Room Unit & Integration Test Suite (`38/38` Tests)
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
- **[CHANGELOG.md](CHANGELOG.md)** — Release notes and version history (`v2.1.0` $\rightarrow$ `v3.9.0`)
- **[docs/request-flow.md](docs/request-flow.md)** — Byte-level walkthrough of a multi-model turn (`Gemini 4 Argon` & `Claude Opus 5.5`)
- **[docs/mcp.md](docs/mcp.md)** — Guide to the 8 built-in FastMCP servers and adding custom MCP tools

---

## 📄 License

MIT — see [LICENSE](LICENSE).
