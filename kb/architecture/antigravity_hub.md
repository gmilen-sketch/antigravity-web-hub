---
okf_version: "0.2"
id: antigravity-web-hub-architecture
title: "Antigravity Web Hub Architecture & Multi-Model Routing"
summary: "Headless GCP Compute-Optimized deployment of Google Antigravity Web with 7-model Vertex AI routing, FastMCP servers, and SQLite-WAL persistence."
type: architecture
status: verified
confidence: 0.99
last_verified: "2026-09-30"
tags: [antigravity, vertex-ai, fastmcp, nginx, iap, architecture]
aliases: [antigravity-hub, ccpa-mock, multi-model-router, language-server]
related_concepts: [autonomy-lifecycle-governance]
sources:
  - id: src-ccpa-mock
    type: code_repo
    title: "src/ccpa_mock.py — 7-Model Allowlisted Enum Router"
    URI: "src/ccpa_mock.py"
    fetched_at: "2026-09-30"
---

# Antigravity Web Hub Architecture & Multi-Model Routing

## Summary

Antigravity Web Hub deploys the standalone Google Antigravity `language_server` (`:8081`) behind an IAP-protected Nginx reverse proxy (`:80` / `:8080`) paired with a Python Vertex AI protocol translation sidecar (`src/ccpa_mock.py` on `:8083`) [^src-ccpa-mock].

## Core Facts & Allowlisted Model Catalog

* **Default Serving Model**: `Gemini 3.8 Flash` (`enum 352` $\rightarrow$ `gemini-3.8-flash`) [^src-ccpa-mock].
* **High-Throughput Tier**: `Gemini 3.5 Flash Lite` (`enum 330` $\rightarrow$ `gemini-3.5-flash-lite`) [^src-ccpa-mock].
* **Deep Reasoning Partner Tier**: `Claude Opus 5 (Vertex AI)` (`enum 290` $\rightarrow$ `claude-opus-5`) and `Claude Sonnet 5 (Vertex AI)` (`enum 333` $\rightarrow$ `claude-sonnet-5`) [^src-ccpa-mock].
* **FastMCP STDIO Servers**: `knowledge_graph`, `autonomy_engine`, `deep_research`, and `google_workspace` [^src-ccpa-mock].

[^src-ccpa-mock]: Verified in `src/ccpa_mock.py` and `scripts/install.sh` (`v3.3.0`).
