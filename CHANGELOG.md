# Changelog

All notable changes to the **Antigravity Web Hub** project will be documented in this file.

---

## [3.6.1] - 2026-10-14 — 🌟 Main Page Architecture Refresh & Full 8-Model GA Catalog (`Gemini 4 Argon`, `Claude Opus 5.5`, `Claude Sonnet 5.5` & `Claude Fable 5`)

### 🚀 Main Landing Page & 8-Model GA Roster Alignment
- **Complete Main Page (`README.md`) & Documentation Refresh (`ARCHITECTURE.md`, ` docs/request-flow.md`, `docs/mcp.md`, `.env.example`)**:
  - Updated the main repository landing page (`README.md`) and technical documentation to showcase the complete **8-Model GA Roster**: **Gemini 4 Argon (`gemini-4-argon`, enum `354`, 1M context, `global`/`us`/`eu` mREP)**, **Gemini 3.8 Flash (`gemini-3.8-flash`, enum `352`)**, **Gemini 3.7 Flash (`gemini-3.7-flash`, enum `350`)**, **Gemini 3.6 Flash (`gemini-3.6-flash`, enum `348`)**, **Gemini 3.5 Flash Lite (`gemini-3.5-flash-lite`, enum `330`)**, **Claude Opus 5.5 (Vertex AI) (`claude-opus-5-5`, enum `290`)**, **Claude Sonnet 5.5 (Vertex AI) (`claude-sonnet-5-5`, enum `333`)**, and **Claude Fable 5 (Next-Gen) (`claude-fable-5`, enum `340`)**.
  - Documented the **Persistent Cross-Browser Multi-Model Sidebar Sessions (`/api/sessions` & `JetboxSubscribeToState` hydration)**, the **Antigravity 2.0 Core Engine (`v2.22.0` Hub + `v1.3.3` CLI + `webm_encoder` + `chrome-devtools-mcp`)**, the **14 Clean-Room Autonomy Pillars**, **20 `PD-Q` Skills**, **8 FastMCP Servers**, **3 Lifecycle Hooks**, and **5 Custom Subagents**.
- **Anthropic Claude 5.5 GA UI & Gateway Alignment (`src/bootstrap.js`, `src/ccpa_mock.py`, `scripts/verify_e2e.js`)**:
  - Updated enum `290` to **`Claude Opus 5.5 (Vertex AI)`** (`claude-opus-5-5`) and enum `333` to **`Claude Sonnet 5.5 (Vertex AI)`** (`claude-sonnet-5-5`) across `DROPDOWN_MODELS`, `defaultCascadeModelConfigData`, `fetchAvailableModels`, and `map_model_name()` while maintaining backward compatibility for `Claude Opus 5` / `Claude Sonnet 5` aliases (`test_27_main_page_readme_and_8_model_ga_catalog_sync`).

---

## [3.6.0] - 2026-10-13 — 🚀 Gemini 4 Argon GA Support (`gemini-4-argon` / Enum `354`), 1M Long-Horizon Reasoning & Strict Parameter Sanitizer

### 🚀 Gemini 4 GA Flagship Integration
- **8-Model GA Roster (`src/bootstrap.js` & `src/ccpa_mock.py`)**:
  - Added **Gemini 4 Argon** (`gemini-4-argon`, numeric proto enum `354`, `1,048,576` combined token window, `65,536` single-turn output cap, `global` / `us` / `eu` multi-region mREP routing) as the top recommended flagship model across UI selectors, `GetUserStatus`, `GetCascadeModelConfig`, `StartCascade`, and `fetchAvailableModels`.
  - Implemented `sanitize_gemini_4_payload()` in `src/ccpa_mock.py` to strip `thinkingBudget`, `candidateCount`, `frequencyPenalty`, and `presencePenalty` and normalize `MINIMAL` $\rightarrow$ `MEDIUM` thinking levels per Gemini 4 GA strict API validation rules (`test_26_gemini_4_argon_ga_routing_and_param_sanitization`).

---

## [3.5.1] - 2026-10-12 — 🔒 Customer Distribution Clean-Room IP & Zero-Binary Certification

### 🛡️ Pre-Distribution Binary, Git History & Terminology Scrub
- **Removed All Pre-Compiled Binaries & Proprietary UI Archives (`0` Binary Blobs in Working Tree & Git History)**:
  - Purged `assets/agyhub_ui_bundle.zip` (`3.05 MB`), `assets/jetbox_ui_bundle.zip` (`6.62 MB`), local `bin/*` binaries (`language_server`, `webm_encoder`, `antigravity`), and `**/__pycache__/*.pyc` bytecode files; re-anchored Git history to a clean single-root commit so `.git/objects/` contains `0` historical binaries or personal emails.
- **Scrubbed Internal Codenames, Project IDs, Cloud Run Service Numbers, URLs & Sandbox IPs (`21` Files Sanitized)**:
  - Replaced internal/unreleased model identifiers (`Claude Fable 5` $\rightarrow$ public GA `Claude Fable 5 (Next-Gen)` / `claude-fable-5`; internal enum string constants $\rightarrow$ numeric proto tags `352`, `350`, `340`).
  - Removed internal Cloud Run auto-updater project number, internal changelist references, personal/sandbox project IDs, internal test domains/identities, personal presentation links, and hardcoded test Load Balancer IPs (`203.0.113.10` RFC 5737 placeholder).
- **Automated Regression Guard (`test_23_customer_distribution_zero_google_ip_or_binaries`)**:
  - Added `test_23` (`23/23` tests passing) certifying `0` non-UTF-8 binary files and `0` SHA-256 matches against internal Google/personal tokens across the entire repository.

---

## [3.5.0] - 2026-10-12 — 🚀 Antigravity 2.0 Core Engine Upgrade (`2.22.0` Hub + `1.3.3` CLI + `2.22.0` Web Bundle) & Official CDN Updater

### 🚀 Antigravity 2.0 Core Runtime & Installer Upgrades
- **Dynamic Official Auto-Updater & Multi-Component Downloader (`scripts/install.sh`)**:
  - Replaced legacy `1.16.5-6703236727046144` CDN tarball extraction and static file-existence skip with dynamic version discovery against `https://storage.googleapis.com/antigravity-public/antigravity-hub/` (`2.22.0-5446056071266304`).
  - Automatically downloads and installs all 4 official Antigravity 2.0 runtime components whenever `$BIN_DIR/.antigravity_version` differs from the latest upstream stamp:
    1. **`language_server` (`v2.22.0`, `183,910,608` bytes)** from `https://storage.googleapis.com/antigravity-public/antigravity-hub/2.22.0-5446056071266304/linux-x64/Antigravity.tar.gz` (`Antigravity-x64/resources/bin/language_server`).
    2. **`webm_encoder` (`v2.22.0`, `17,056,035` bytes)** native WebM browser session recording encoder (`Antigravity-x64/resources/bin/webm_encoder`).
    3. **`chrome-devtools-mcp` (`v2.22.0`)** built-in browser agent MCP package (`Antigravity-x64/resources/app.asar.unpacked/node_modules/chrome-devtools-mcp`).
    4. **`antigravity` Standalone CLI (`v1.3.3`, `214,237,392` bytes, build `5524738307653632`)** from `https://storage.googleapis.com/antigravity-public/antigravity-cli/1.3.3-5524738307653632/linux-x64/cli_linux_x64.tar.gz` (`/usr/local/bin/antigravity`), plus static asset mirroring from `https://antigravity.static.usercontent.goog/web/2.22.0/` and SHA-256 attestation in `antigravity-release.json`.
- **Antigravity 2.0 Control-Plane & Gateway Compatibility (`src/ccpa_mock.py`, `config/nginx.conf`, `config/start_hub.sh`, `src/bootstrap.js`, `scripts/verify_e2e.js`)**:
  - Added `--override_ide_name="antigravity"` and `--override_ide_version="2.22.0"` to `config/start_hub.sh`.
  - Added `/healthz` reverse-proxy routing (`http://127.0.0.1:8081/healthz`) and `/antigravity-release.json` static endpoint to `config/nginx.conf`.
  - Added `GET /api/version`, `POST /v1internal:retrieveUserQuotaSummary`, `POST /exa.language_server_pb.LanguageServerService/JetboxWriteState`, `/v1internal/{agentPlugins,buildWithGooglePlugins,cascadeNuxes}` JSON catalog endpoints, and Antigravity 2.0 client feature flags (`enable-jetbox-terminal-v2`, `remote-control-setting-enabled`) to `src/ccpa_mock.py`.
  - Added `test_22_antigravity_2_0_core_upgrade_and_version_api` (`22/22` unit/integration tests) and live `/api/version` + `/healthz` assertions in `scripts/verify_e2e.js`.

---

## [3.4.0] - 2026-10-12 — 🛡️ Clean-Room Autonomy Engine v3.4.0: 14 Core Pillars, 20 PD-Q Skills, Hybrid Graph-RAG & Zero-IP Certification

### 🚀 Major Additions & Clean-Room Transpositions (`Bucket A` & `Bucket B` — 100% Open-Source / Public Cloud APIs)
- **Pillar 1 — Turn-1 Pinned KV-Cache `PreInvocation` Hook (`src/hooks/kg_pre_invocation_hook.py` `v3.5`)**:
  - Added pure-Python Porter stemmer (`stem_token`), `0.05`-grid confidence quantization (`quantize_confidence_005`), 2-hop associative neighborhood expansion (`collect_2hop_neighborhood`), canary header stripping (`strip_canary_headers`), and DSO Subagent Orientation Banner (`build_dso_subagent_orientation_banner`).
- **Pillar 2 — 2-Stage Stateless Goldfish $\rightarrow$ Isolated Judge `Stop` Gate (`src/hooks/agent_stop_black_hat_gate.py` `v4.8`)**:
  - Added `C9` Pre-Prose Table Readback Gate (`check_c9_pre_prose_table_gate`), Chat Bottom-Up Pyramid & `### ⚡ TL;DR` validator (`check_chat_bottom_up_tldr_structure`), Git Diff Anti-Test-Tampering Auditor (`audit_git_diff_test_tampering`), and Subagent Proof Freshness check (`verify_subagent_proof_freshness`).
- **Pillar 3 — `PreToolUse` Sentinel Dispatcher (`src/hooks/sentinel_dispatch.py` `v2.0` & `src/hooks/rules/`)**:
  - Added `r31_hook_integrity_guard.py` (blocks unauthorized modification of governance hooks), `audit_skill_hook_safety.py`, `zero_latex.py`, and expanded `rule_11_anonymization.py`.
- **Pillar 4 — P0 Quality-First Runtime Engine (`src/autonomy_engine/p0_quality_first_engine.py` `v2.5`)**:
  - Added `CB-8` Bernstein Disjoint Write-Set Verifier (`verify_bernstein_disjoint_write_sets`), 4-Tier Hierarchical Rule Precedence Sorter (`sort_rules_by_precedence`), Deterministic Relative Temporal Resolver (`resolve_temporal_window`), and Chained Subshell Auditor (`audit_chained_shell_subshells`).
- **Pillar 5 — P1 Quality-First Runtime Engine (`src/autonomy_engine/p1_quality_first_engine.py` `v2.5`)**:
  - Added `P1-CB-8` Prompt-Injection Context Firewall (`scan_retrieved_chunks_for_prompt_injection`), Strict Primary-Source Abstention Gate (`verify_strict_source_abstention`), and 3-Stage Issue Triage Funnel (`triage_issue_3stage`).
- **Pillar 6 — 6-Field BM25F + Hybrid Graph-RAG Polyphonic Retriever (`src/autonomy_engine/polyphonic_retriever.py` `v2.0`)**:
  - Upgraded to 6-field weighted BM25F (`id`, `title`, `headers`, `tags`, `aliases`, `body`) with Hybrid Graph-RAG structural boost ($\alpha \cdot \text{BM25F} + (1-\alpha) \cdot \text{GraphBoost}$), line-numbered chunking (`format_line_numbered_chunk`), and AST/Markdown outline extraction (`extract_document_outline`).
- **Pillar 7 — Phase-1 Self-Grill Bayesian Prior Engine (`src/autonomy_engine/grill_me_prior_engine.py` `v2.5`)**:
  - Added 4-tier `C0..C3` ambiguity classifier and autonomous `<self_grill_locked_spec>` compiler with Elo prior tracking (`/dev/shm/grill_me_priors.json`).
- **Pillar 8 — Multi-Loop Web UI & SVG Geometry Auditor (`src/playwright_scraper/audit_web_ui_geometry.py` `v2.0`)**:
  - Enforces 5 DOM/SVG geometry checks (`svg_text_outside_box`, `svg_line_cuts_card`, `svg_line_cuts_text`, `svg_sibling_box_overlap`, `html_box_overflow`) plus `fitAllSvgTextToBoxes(root)` runtime clamping.
- **Pillar 9 — Unified 14-Mode Evaluation Router & Skillgrade Engine (`src/autonomy_engine/unified_eval_router.py` `v2.5`)**:
  - Supports 14 evaluation modes (`auto`, `fast`, `replay`, `skill-ab`, `tripartite-uroboros`, `panel-bt-consensus`, `paired-stat-diff`, `zero-flake-11pass`, etc.) with Bradley-Terry Elo, McNemar exact test, and `Skillgrade` (`SG-1..SG-5`) scoring, plus `delphi_six_hats_task_router.py`, `trope_scanner.py`, and `snapshot_guard.py`.
- **Pillar 10 — Nightly Dreaming Engine v5.2 & Workspace Hygiene (`src/knowledge_graph/dreaming_engine.py`, `src/autonomy_engine/workspace_hygiene_gate.py`)**:
  - Added 4-Axis Trajectory Backtracking (`backtrack_trajectory_4axis`), Incremental JSONL Byte-Offset Watermark Reader (`read_incremental_jsonl_watermark`), Bitemporal KG (`kg_bitemporal_engine.py`), $k$-hop BFS traversal (`kg_traversal_engine.py`), and interactive 3D/SVG viewer (`knowledge_graph_explorer.html`).
- **Pillar 11–14 — Clean-Room Workspace Adapter (`agent_ssot_formatter.py`), BENTO Diagram Compiler (`render_gcp_draw.py` `v15.5`), Standalone RFC 6455 CDP Navigator (`cdp_navigator.py` `v2.0`), & 20 Clean-Room Skills (`skills/`)**:
  - Expanded `skills/` from 8 to 20 clean-room customer skills (`PD-Q` headers + `EVAL.txtpb` + `references/pdq-extended-guide.md` + `skills/manifest.json`) and certified **0 internal tokens** across all 4 public repositories via `test_20`.

---

## [3.3.0] - 2026-09-30 — 🧠 Open Knowledge Format (OKF v0.2), 2-Stage Goldfish-Judge Gate v4.3, P0/P1 Quality Engines & 5-Subagent Roster

### 🚀 Major Additions & Clean-Room Ports (`AGW-1` – `AGW-5`)
- **Security Remediation (`src/ccpa_mock.py` — Issue #23 / `CWE-918`)**: Added `validate_upstream_url()` (`urllib.parse.urlsplit` validation asserting `scheme == 'http'`, `hostname == '127.0.0.1'`, `port == 8081`, and `username is None`) and `sanitize_forwarded_headers()` stripping `Metadata-Flavor` and `X-Google-Metadata-Request` headers across `forward_request` and `forward_and_stream`.
- **`AGW-1` (Lifecycle Hooks Upgrade — `src/hooks/`)**:
  - **2-Stage Stateless Goldfish $\rightarrow$ Isolated Judge `Stop` Gate (`agent_stop_black_hat_gate.py` `v4.3`)**: Enforces `C1–C8` forensic verification contracts across `black-hat-goldfish` and `black-hat-judge`, retains single-stage `black-hat-critic` fallback unless `BH_GATE_STRICT_TWO_STAGE=1`, adds in-process attached verification (`run_attached_black_hat_verification`), pre-critic bottom summary gate, and `(?<![>-])>>?` arrow guard.
  - **Turn-1 Pinned KV-Cache `PreInvocation` Hook (`kg_pre_invocation_hook.py` `v3.3`)**: Strips `<CONTEXT_SUMMARY>` before entity matching, enforces `score >= 45`, returns `{}` on zero matches, traverses 1-hop associative edges, supports `aliases[]`, and co-bundles Top-3 `okf:*` concept dossiers.
  - **`PreToolUse` Sentinel Dispatcher (`sentinel_dispatch.py` & `rules/`)**: Modular rule plugins enforcing `destructive_commands.py`, `deprecated_models.py`, `file_bounds.py`, and `rule_11_anonymization.py`.
- **`AGW-2` (5-Subagent Clean-Room Roster — `agents/`)**:
  - Added `black-hat-goldfish`, `black-hat-judge`, `dreaming-improvement-reasoner`, `workspace-housekeeper`, and upgraded `black-hat-critic`.
- **`AGW-3` (Open Knowledge Format `OKF v0.2`, P0/P1 Quality Engines & Dreaming `v5.2`)**:
  - Added `src/knowledge_graph/okf_knowledge_compiler.py`, `src/knowledge_graph/validate_okf.py`, `src/knowledge_graph/kg_serving_cache.py`, and public `kb/` bundle (`kb/index.md`, `kb/log.md`, `kb/architecture/antigravity_hub.md`, `kb/guides/autonomy_lifecycle.md`).
  - Added `src/autonomy_engine/p0_quality_first_engine.py` (`CB-1..CB-7`), `src/autonomy_engine/p1_quality_first_engine.py` (`P1-CB-1..P1-CB-7`), `src/autonomy_engine/workspace_hygiene_gate.py`, and upgraded `src/autonomy_engine/anti_overfitting_gate.py` with the 8-mutant adversarial saboteur benchmark (`100%` recall).
  - Upgraded `src/knowledge_graph/dreaming_engine.py` to `v5.2` integrating OKF v0.2 compilation, Saboteur filtering, and `/dev/shm/dreaming_improvements_for_reasoner.json` emission.
- **`AGW-4` (`PD-Q` Skills, `EVAL.txtpb` & Diagram Renderer `v15.2`)**:
  - Added `src/diagram_renderer/render_gcp_draw.py` (`v15.2`) and upgraded `render_mermaid.py` and `diagram_mcp_server.py`.
  - Upgraded all 8 skills in `skills/` with `## Epistemic Reasoning & Grounding Protocol (PD-Q)` headers, `EVAL.txtpb` specifications, and `references/pdq-extended-guide.md`.
- **`AGW-5` (Install/Startup Wiring & 10-Test Suite)**:
  - Updated `scripts/install.sh`, `src/start_hub.sh`, `config/start_hub.sh`, and expanded `tests/test_autonomy_kg_hooks.py` to 10 comprehensive unit/integration tests.

---

## [3.2.2] - 2026-09-21 — 🎯 7-Model UI Dropdown Allowlist Mapping & End-to-End Streaming

### 🚀 Fixes & Model Routing Enhancements
- **Allowlisted `language_server` Enum Mapping (`src/ccpa_mock.py`)**: Mapped all 7 UI dropdown models to native allowlisted `language_server` enums so interactive UI prompts stream end-to-end without protocol envelope drops:
  - `Gemini 3.8 Flash` (Default) $\rightarrow$ `enum 352` (`352` $\rightarrow$ `gemini-3.8-flash`)
  - `Gemini 3.7 Flash` $\rightarrow$ `enum 350` (`350` $\rightarrow$ `gemini-3.7-flash`)
  - `Gemini 3.6 Flash` $\rightarrow$ `enum 348` (`MODEL_GOOGLE_GEMINI_2_5_FLASH` $\rightarrow$ `gemini-3.6-flash`)
  - `Gemini 3.5 Flash Lite` $\rightarrow$ `enum 330` (`MODEL_GOOGLE_GEMINI_2_5_FLASH_LITE` $\rightarrow$ `gemini-3.5-flash-lite`)
  - `Claude Opus 5 (Vertex AI)` $\rightarrow$ `enum 290` (`MODEL_CLAUDE_4_OPUS` $\rightarrow$ `claude-opus-5`)
  - `Claude Sonnet 5 (Vertex AI)` $\rightarrow$ `enum 333` (`MODEL_CLAUDE_4_5_SONNET` $\rightarrow$ `claude-sonnet-5`)
  - `Claude Fable 5 (Next-Gen)` $\rightarrow$ `enum 340` (`MODEL_CLAUDE_4_5_HAIKU` $\rightarrow$ `claude-fable-5`)

---

## [3.2.1] - 2026-09-21 — ⚡ Gemini 3.8 Flash (Default), Claude Opus 5 & Claude Sonnet 5

### 🌟 Model Catalog Upgrades
- **Production Model Upgrades (`src/ccpa_mock.py`)**: Enabled **Gemini 3.8 Flash** as default production model alongside **Claude Opus 5 (Vertex AI)** and **Claude Sonnet 5 (Vertex AI)** across UI dropdown rendering and Vertex AI forwarding.

---

## [3.2.0] - 2026-09-20 — 🧠 Clean-Room Autonomy Suite, Black-Hat Stop Gate & Zero-Loss Upgrades

### 🚀 Major Additions & Clean-Room Ports
- **Turn-0 `PreInvocation` Grounding Hook (`src/hooks/kg_pre_invocation_hook.py`)**: Automatically injects entity properties from `/dev/shm/kg_warm_cache.json` before turn generation in $<1\,\text{ms}$.
- **Black-Hat Critic `Stop` Hook Gate v3.0 (`src/hooks/agent_stop_black_hat_gate.py`)**: Enforces turn-scoped default-deny on state mutations, requiring independent subagent verification (`agents/black-hat-critic/agent.md`, $\ge 2$ tool steps + `CRITIC_VERDICT: APPROVED`), self-throttling at `MAX_FORCED_CONTINUATIONS = 2`.
- **Nightly Dreaming v4.0 Upgrades (`src/knowledge_graph/dreaming_engine.py`)**:
  - Added Anderson ACT-R power-law decay with clamping floor ($A_{\min} = -2.0$) in `kg_decay_link_predictor.py`.
  - Ported 2-Tier Resilient Steer Harvester (`resilient_steer_harvester.py`) with SHA-256 content-hashed idempotent graph absorption.
  - Ported 16-pattern Session Efficiency & Token Waste Analyzer (`session_waste_analyzer.py`).
  - Added AAAK 3-Pass Compressor CoT preservation fix (`thinking` + `thought` keys).
- **Clean-Room Provisioning & Non-Destructive Upgrades**:
  - Updated `scripts/install.sh` to create default workspace directories (`$RUN_HOME/enterprise-workspace` & `$RUN_HOME/workspace`) so `StartCascade` never fails with `file does not exist` on fresh VMs.
  - Added non-destructive state check preserving existing `antigravity_state.pbtxt`, `conversations/`, and `knowledge_graph.json` when upgrading live instances.
  - Enforced `export CLOUDSDK_CORE_ACCOUNT` in `gcp_setup_vm.sh` and `gcp_setup_lb.sh`.

---

## [3.1.1] - 2026-08-24 — 🛠️ Standalone Binary Packaging & In-Browser Resilience

### 🛠️ Production Fixes & Hardening
- **Bundled Standalone `language_server` Binary**: Bundled verified Go `language_server` binary directly in `bin/` and updated `scripts/install.sh` to prioritize repository packages over Google CDN downloads, preventing extension server flag incompatibility (`--subclient_type=hub`).
- **Anthropic Model Garden 404 Auto-Fallback**: Integrated automatic failover to `gemini-3.7-flash` in `src/ccpa_mock.py` when target GCP projects lack Anthropic Model Garden Marketplace enablement.
- **Compute Tier Upgrade**: Default instance upgraded from `c2-standard-8` to `c2-standard-16` (16 vCPUs, 64 GB RAM), reducing Time-to-Initial-Render (TTIR) by 41.6% (from 6.80s to 3.97s).
- **Persistent Stream Headless In-Browser Testing**: Standardized `scripts/verify_e2e.js` and `playwright-cdp` invocations with `waitUntil: "none"` to prevent navigation timeouts on long-lived gRPC chunked streams (`JetboxSubscribeToSummaries`, `JetboxSubscribeToState`, `ProjectUpdatesStream`).
- **Dynamic Binary & Module Resolution**: Updated `scripts/verify_e2e.js` with multi-path `ws` resolution and automatic Chrome/Chromium binary discovery across environments.

---

## [3.1.0] - 2026-08-21 — 🚀 Multi-Model Routing, FastMCP & Clean-Room Automation

### 🌟 Major Enhancements
- **Dynamic Multi-Model Catalog Routing (`src/ccpa_mock.py`)**: Real-time intercept and model translation supporting `Gemini 3.7 Flash`, `Gemini 3.6 Flash`, `Gemini 3.5 Flash Lite`, `Claude 3.7 Sonnet`, `Claude Opus 5`, and `Claude Fable 5`.
- **FastMCP Protocol Implementation**: Migrated all auxiliary tools to standard Model Context Protocol (MCP) servers (`transport="stdio"`):
  - `knowledge_graph`: SQLite-WAL property graph with ACT-R decay and `/dev/shm/` fast cache.
  - `autonomy_engine`: AAAK 3-pass token compression, 4-voice polyphonic factual search, and context envelope hydration.
  - `deep_research`: Agentic research loop with live search and web fetch.
  - `google_workspace`: Native asynchronous Gmail, Calendar, Drive, and Sheets operations.
- **Compute-Optimized `c2-standard-8` Infrastructure**: Default VM upgraded to 8 vCPUs / 32 GB RAM for responsive language server compilation and 8-worker Nginx reverse proxy dispatch.
- **Single-Command Destroy $\rightarrow$ Deploy $\rightarrow$ Verify Pipeline (`scripts/deploy_and_verify.sh`)**: Fully automated clean-room orchestration with automated Headless Chrome CDP browser verification, prompt submission, and live thread validation.
- **Community Skills Catalog**: Bundled 8 pre-configured agent skills in `skills/` with automated multi-path discovery (`~/.gemini/config/skills/`, `.agents/skills/`, and `skills.json`).
- **Storage Bridge & Zero-Friction Onboarding**: Automated `antigravity_state.pbtxt` initialization and Nginx `<head>` injection of `window.nativeStorage` and `window.electronNative` polyfills.

---

## [3.0.0] - 2026-07-22 — 🌟 Official First Stable Release

### 🚀 Production Highlights
- **First Stable Production Release**: Verified 100% end-to-end operational stability across full infrastructure lifecycle (clean teardown, 1-shot declarative Terraform provisioning, dynamic zone auto-discovery, systemd daemon management, and live Vertex AI streaming inference).
- **5th Gen Intel Emerald Rapids N4 Migration**: Default compute instance upgraded to **`n4-standard-2`** with automated Google Cloud **`hyperdisk-balanced`** storage engine for maximum memory bandwidth and sub-millisecond model routing.
- **Automated Google Cloud API Activation**: Declarative Terraform resources (`google_project_service`) and shell scripts automatically enable all 6 required Google Cloud APIs (`compute`, `iap`, `aiplatform`, `iam`, `cloudresourcemanager`, `serviceusage`) with zero manual GCP Console clicks.
- **Enterprise GCP Sandbox Org Policy Compliance**: Fully certified for Google Cloud Enterprise GCP Sandbox sandbox environments, enforcing `constraints/compute.requireShieldedVm`, `compute.requireOsLogin`, `compute.vmExternalIpAccess`, and `compute.skipDefaultNetworkCreation`.
- **Dynamic VM Zone Auto-Discovery**: Automatic GCP zone resolution across `bootstrap_all.sh`, `gcp_setup_vm.sh`, and `gcp_setup_lb.sh`, preventing SSH-over-IAP and archive transfer failures in non-default regions.
- **Automated PR & GitFlow Management**: Added `scripts/auto_merge_pr.py` for automated Pull Request creation and instant merging via GitHub REST API without web UI bottlenecks.

---

## [2.2.0] - 2026-07-22

### 🚀 Added
- **N4 Machine Type Family Migration**: Upgraded default VM machine type from `e2-standard-2` to `n4-standard-2` (5th Gen Intel Xeon Emerald Rapids) across Terraform (`variables.tf`, `terraform.tfvars`), setup scripts (`gcp_setup_vm.sh`), and environment configurations for significantly higher memory bandwidth and faster model routing.
- **Automated Google Cloud API Enablement**: Added declarative `google_project_service` resources in Terraform (`terraform/main.tf`) and automated `gcloud services enable` calls across all shell scripts (`scripts/gcp_setup_vm.sh`, `scripts/gcp_setup_lb.sh`). This automatically activates the 6 core required Google APIs on any fresh project:
  1. `compute.googleapis.com` (Compute Engine API)
  2. `iap.googleapis.com` (Cloud Identity-Aware Proxy API)
  3. `aiplatform.googleapis.com` (Vertex AI API)
  4. `iam.googleapis.com` (Identity and Access Management API)
  5. `cloudresourcemanager.googleapis.com` (Cloud Resource Manager API)
  6. `serviceusage.googleapis.com` (Service Usage API)

---

## [2.1.0] - 2026-07-21

### 🚀 Added
- **1-Click Terraform Module**: Declarative infrastructure provisioning with Enterprise GCP Sandbox policy compliance (`compute.requireShieldedVm`, `compute.requireOsLogin`, `compute.vmExternalIpAccess`, `compute.skipDefaultNetworkCreation`).
- **Tier 2 Google CDN Binary Download Fallback**: Added automatic resolution in `bootstrap_all.sh` to download `Antigravity.tar.gz` directly from Google's official CDN (`https://edgedl.me.gvt1.com/...`) and extract `language_server` when deploying from a fresh workstation without local binaries.
- **Automated Vertex AI IAM Binding**: Terraform module and setup scripts now automatically bind `roles/aiplatform.user` (`aiplatform.endpoints.predict`) to the Compute Engine default service account (`<project_number>-compute@developer.gserviceaccount.com`).
- **Standalone Go `language_server` Packaging**: Included native Go server binary detection and packaging in `scripts/bootstrap_all.sh`.

### 🛠️ Fixed
- **Vertex AI GCE Metadata Server Token Resolution**: Updated `get_adc_token()` in `src/ccpa_mock.py` to query GCE Metadata Server (`http://metadata.google.internal/...`) first, guaranteeing `roles/aiplatform.user` IAM permissions for Vertex AI streaming model inference without relying on local workstation credentials.
- **Enterprise GCP Sandbox Org Policy Domain Restrictions**: Added explicit guidance and comments in `terraform/terraform.tfvars.example` and `SETUP.md` specifying the use of Enterprise GCP Sandbox Admin user accounts (`admin@...example.com`) to comply with `constraints/iam.allowedPolicyMemberDomains`.
- **Auth RPC Interception & Onboarding Bypass**: Added Nginx location rules for `GetAuthStatus`, `HasAuthToken`, `LoginWithBrowser`, `fetchUserInfo`, `loadCodeAssist`, `fetchAdminControls`, and `fetchAvailableModels` proxying to `ccpa_mock.py` (`:8083`), fixing SPA client-side redirects to `/onboarding`.
- **CSRF Token Alignment**: Standardized `CSRF_TOKEN=antigravity_secret_csrf_token_12345` across `.env.example`, `start_hub.sh`, `/etc/antigravity-web.env`, and `config/nginx.conf`, eliminating `Grpc-Status: 16 (invalid CSRF token)` errors.
- **Model Dropdown Proto3 Choice Wrappers**: Formatted model choice enums (`348` Gemini 3.5 Flash, `330` Gemini 3.1 Flash Lite Preview, `343` Gemini 3.1 Pro) using `{choice: {case: "model", value: val}}` for `@bufbuild/protobuf` compatibility in the browser.
- **gcloud ECP Socket Leak Handling**: Added `pkill -9 -f "ecp"` and `pkill -9 -f "gcloud"` in retry wrappers to resolve `[Errno 98] Address already in use` socket errors.
- **Terraform Unmanaged Instance Group Self-Link**: Fixed `instances` parameter in `google_compute_instance_group.unmanaged_ig` to use `google_compute_instance.hub_vm.self_link`.

