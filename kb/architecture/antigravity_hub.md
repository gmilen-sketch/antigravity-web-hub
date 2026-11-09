---
okf_version: "0.2"
id: antigravity-web-hub-architecture
title: "Antigravity Web Hub v3.9.0 Architecture, 4-Plane Topology & 8-Model Router"
summary: "Self-documentation for Antigravity Web Hub v3.9.0: Nginx (:8080), headless Go language_server v2.29.1 (:8081), 8-Model Vertex AI ADC router ccpa_mock.py (:8083), 8 FastMCP servers (:8084), /api/sessions persistence, and /dev/shm/agw_kg_warm_cache.json."
type: architecture
status: verified
confidence: 0.99
last_verified: "2026-11-09"
tags: [antigravity, web-hub, vertex-ai, fastmcp, nginx, iap, architecture, language-server]
aliases: [antigravity-hub, antigravity web hub, ccpa-mock, multi-model-router, language-server, start_hub, bootstrap.js]
related_concepts: [autonomy-lifecycle-governance, gemini-models-and-vertex-api, antigravity-cli-and-sdk, google-adk-and-a2a-protocol]
sources:
  - id: src-ccpa-mock
    type: code_repo
    title: "src/ccpa_mock.py — 8-Model GA Vertex AI Router & Session Store"
    URI: "src/ccpa_mock.py"
    fetched_at: "2026-11-09"
  - id: src-start-hub
    type: code_repo
    title: "config/start_hub.sh & config/nginx.conf — 4-Plane Runtime Topology"
    URI: "config/start_hub.sh"
    fetched_at: "2026-11-09"
---

# Antigravity Web Hub v3.9.0 Architecture, 4-Plane Topology & 8-Model Router

## 1. Runtime Topology & Port Map

Antigravity Web Hub (`v3.9.0`) deploys the official Google Antigravity `2.29.1` Web UI and `1.5.3` CLI as a cloud-hosted, multi-model agentic IDE [^src-ccpa-mock] [^src-start-hub]:

* **Ingress & Web Proxy Plane (`:80` / `:8080` — Nginx + `src/bootstrap.js`)**:
  - Serves the static React SPA bundle (`/var/www/html/web-assets/main.js`), injects `/bootstrap.js`, and enforces `proxy_set_header Host "127.0.0.1:8081"` so the upstream Go `language_server` accepts localhost-only Connect-RPC requests [^src-start-hub].
  - Exposes `/healthz` readiness checks and `/api/version` release metadata (`antigravity-release.json`).
* **Core Agent Engine Plane (`:8081` — Go `language_server` `v2.29.1`)**:
  - Runs headless with `--subclient_type=hub --override_ide_version="2.29.1" -standalone` and SQLite WAL conversation stores (`~/.gemini/antigravity/conversations/*.db`, `src/ensure_wal.py`) [^src-start-hub].
* **8-Model Vertex AI Translation Gateway (`:8083` — `src/ccpa_mock.py`)**:
  - Translates Connect-RPC / gRPC-Web streams into Google Cloud Vertex AI `streamGenerateContent` and Anthropic `streamRawPredict` calls using VM Service Account Application Default Credentials (ADC) [^src-ccpa-mock].
  - Persists cross-browser sidebar conversations via `GET /api/sessions` and `POST /api/sessions` (`/mnt/data/projects/persistent_ui_sessions.json`) with monotonic step-count protection (`len(new_steps) >= len(existing_steps)`) [^src-ccpa-mock].
* **FastMCP & Memory Plane (`:8084` / STDIO — `mcp_config.json`)**:
  - Runs 8 clean-room MCP servers (`knowledge-graph`, `autonomy-engine`, `deep-research`, `diagram-renderer`, `browser-cdp`, `cloud-telemetry`, `workspace-docs`, `filesystem`) with `_meta: {"antigravity/alwaysLoad": true}` (`EAGER_TOOL_META`) and sub-millisecond shared-memory caching at `/dev/shm/agw_kg_warm_cache.json` (`KG_WARM_CACHE_PATH`).

## 2. Key Operational Invariants

* **CSRF & Origin Header Injection (`sanitize_forwarded_headers`)**: Every proxied RPC to `:8081` includes `Host: 127.0.0.1:8081`, `Origin: http://127.0.0.1:8081`, and `x-codeium-csrf-token` while stripping `Metadata-Flavor` and userinfo `@169.254.169.254` SSRF vectors (`CWE-918`) [^src-ccpa-mock].
* **Custom OAuth 2.0 IAP for Trial Orgs (`Error 604` Fix)**: On GCP projects without a Google Workspace `directoryCustomerId`, bind a custom **External** Web Application OAuth 2.0 client (`https://iap.googleapis.com/v1/oauth/clientIds/<CLIENT_ID>:handleRedirect`) to the backend service.

[^src-ccpa-mock]: Verified in `src/ccpa_mock.py` (`v3.9.0`).
[^src-start-hub]: Verified in `config/start_hub.sh`, `config/nginx.conf`, and `scripts/install.sh` (`v3.9.0`).
