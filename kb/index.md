---
okf_version: "0.2"
id: antigravity-kb-index
title: "Antigravity Web Hub v3.9.0 — Open Knowledge Format (OKF v0.2) Index"
summary: "Root entry point for the Antigravity Web Hub v3.9.0 Open Knowledge Format (OKF v0.2) foundational documentation bundle covering Web Hub architecture, lifecycle hooks, Gemini/Vertex AI models, Google ADK, and Antigravity CLI/SDK."
type: overview
status: verified
confidence: 1.0
last_verified: "2026-11-09"
tags: [okf, antigravity, knowledge-graph, architecture, autonomy, gemini, adk, agents-cli]
---

# Antigravity Web Hub v3.9.0 — Open Knowledge Format (`OKF v0.2`) Bundle

This directory implements the public **Open Knowledge Format (`OKF v0.2`)** specification ([GoogleCloudPlatform/knowledge-catalog/tree/main/okf](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)) providing out-of-the-box, zero-secret self-documentation and developer reference dossiers for Antigravity Web Hub.

## Indexed Foundational Dossiers (`5` Verified `OKF v0.2` Dossiers)

1. **[Architecture: Antigravity Web Hub v3.9.0 Topology](architecture/antigravity_hub.md)** (`okf:antigravity-web-hub-architecture`) — 4-plane runtime topology (`:8080` Nginx, `:8081` Go `language_server` `v2.29.1`, `:8083` `ccpa_mock.py` 8-Model router, `:8084` FastMCP servers), `/api/sessions` persistence, and `/dev/shm/agw_kg_warm_cache.json`.
2. **[Guide: Autonomous Governance, Dual-Mode Harness & 20 PD-Q Skills](guides/autonomy_lifecycle.md)** (`okf:autonomy-lifecycle-governance`) — `PreInvocation` Dual-Mode Classifier (`SWE_BENCHMARK_MODE` vs `PORTFOLIO_MODE`), `PreToolUse` Sentinel, 2-Stage Stateless Goldfish $\rightarrow$ Isolated Judge `Stop` gate, 14 Wave-12 kernels (`AGW-W12-01`..`14`), and `scripts/run_ab_benchmark.py`.
3. **[Reference: Gemini & Vertex AI Model Catalog & API Contracts](reference/gemini_models_and_vertex_api.md)** (`okf:gemini-models-and-vertex-api`) — 8-Model GA catalog (`Gemini 4 Argon` enum `354`, `Gemini 3.8 Flash`, `Gemini 3.5 Flash`, `Gemini 3.6/3.5 Flash`, `Claude Opus/Sonnet 5.5`, `Claude Fable 5`), embeddings/media/open models, and `sanitize_gemini_4_payload()` parameter rules.
4. **[Reference: Google Agent Development Kit (ADK / `google-adk`) & A2A Protocol](reference/google_adk_and_a2a_protocol.md)** (`okf:google-adk-and-a2a-protocol`) — `LlmAgent`, `SequentialAgent`, `ParallelAgent`, `LoopAgent`, `McpToolset`, `FunctionTool`, `adk web`/`run`/`api_server`, Vertex AI Agent Engine deployment, and A2A JSON-RPC schemas.
5. **[Reference: Antigravity CLI v1.5.3 (`agents-cli`) & Python SDK (`google-antigravity`)](reference/antigravity_cli_and_sdk.md)** (`okf:antigravity-cli-and-sdk`) — CLI flags, `LocalAgentConfig().eval()`, `ATIF-v1.7` trajectories, `hooks.json` & `plugin.json` contracts, and Harbor 3P benchmark flags.
