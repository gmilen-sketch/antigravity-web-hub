---
okf_version: "0.2"
id: gemini-models-and-vertex-api
title: "Gemini & Vertex AI Model Catalog, Proto Enums & API Parameter Contracts"
summary: "Reference documentation for the 8-Model GA catalog (Gemini 4 Argon, Gemini 3.8 Flash, Gemini 3.5 Flash, Gemini 3.6/3.5 Flash, Claude Opus/Sonnet 5.5, Claude Fable 5), multimodal/embedding/open models, and sanitize_gemini_4_payload() API rules."
type: reference
status: verified
confidence: 0.99
last_verified: "2026-11-09"
tags: [gemini, vertex-ai, claude, models, thinking-config, embeddings, imagen, veo, gemma]
aliases: [gemini models, model catalog, vertex ai models, gemini-4-argon, gemini-3.8-flash, claude-opus-5-5, sanitize_gemini_4_payload, thinkingLevel]
related_concepts: [antigravity-web-hub-architecture, google-adk-and-a2a-protocol, antigravity-cli-and-sdk]
sources:
  - id: src-model-router
    type: code_repo
    title: "src/ccpa_mock.py — DROPDOWN_MODELS, map_model_name & sanitize_gemini_4_payload"
    URI: "src/ccpa_mock.py"
    fetched_at: "2026-11-09"
  - id: src-deprecated-guard
    type: code_repo
    title: "src/hooks/rules/deprecated_models.py — Active Model Tier Enforcement"
    URI: "src/hooks/rules/deprecated_models.py"
    fetched_at: "2026-11-09"
---

# Gemini & Vertex AI Model Catalog, Proto Enums & API Parameter Contracts

## 1. Active 8-Model GA Catalog in Antigravity Web Hub (`src/ccpa_mock.py`)

Antigravity Web Hub maps `language_server` protobuf model enums directly to Vertex AI endpoints [^src-model-router]:

| UI Model Label | Proto Enum | Vertex AI Model ID | Context / Max Output | Recommended Workload Tier |
| :--- | :---: | :--- | :---: | :--- |
| **`Gemini 4 Argon`** *(Default GA)* | `354` | `gemini-4-argon` | `1,048,576` / `131,072` | Flagship 1M-context reasoning across `global`, `us`, and `eu` mREP |
| **`Gemini 3.8 Flash`** *(Recommended)* | `352` | `gemini-3.8-flash` | `1,048,576` / `131,072` | Default general production multimodal reasoning, coding, and tool use |
| **`Gemini 3.5 Flash`** | `350` | `gemini-3.5-flash` | `1,048,576` / `65,535` | Long-GA production & EU data-residency (`eu` multi-region) execution |
| **`Gemini 3.6 Flash`** | `348` | `gemini-3.6-flash` | `1,048,576` / `131,072` | General production workflows and parallel subagent swarms |
| **`Gemini 3.5 Flash Lite`** | `330` | `gemini-3.5-flash-lite` | `1,048,576` / `65,536` | High-throughput classification, routing, and sub-110ms extraction |
| **`Claude Opus 5.5 (Vertex AI)`** | `290` | `claude-opus-5-5` | `200,000` / `16,384` | Deep architectural synthesis on Vertex AI (`streamRawPredict`) |
| **`Claude Sonnet 5.5 (Vertex AI)`** | `333` | `claude-sonnet-5-5` | `200,000` / `16,384` | High-precision code generation and diff review on Vertex AI |
| **`Claude Fable 5 (Next-Gen)`** | `340` | `claude-fable-5` | `200,000` / `16,384` | Low-latency partner subagent execution on Vertex AI |

## 2. Specialized Media, Embedding & Open-Weight Model Identifiers

* **Embeddings**: `gemini-embedding-001` (text embeddings) and `gemini-embedding-2` (multimodal embeddings) [^src-deprecated-guard].
* **Image & Video Generation**: `imagen-3.0-generate-002` (image generation) and `veo-3.1-lite` (video generation) [^src-deprecated-guard].
* **Open-Weight Models**: `gemma-3` (`1B`, `4B`, `12B`, `27B`), `gemma-4-26b-a4b-it`, and `paligemma-2` [^src-deprecated-guard].
* **Active Model Tier Policy (`src/hooks/rules/deprecated_models.py`)**: All retired 1.x / 2.x Gemini checkpoints, legacy PaLM endpoints, and retired pre-5.x Claude identifiers are automatically blocked by the `PreToolUse` Sentinel hook in favor of the active `3.5+` and `4` Gemini and `5.5` Claude tiers [^src-deprecated-guard].

## 3. Gemini 4 Vertex AI Parameter Contract (`sanitize_gemini_4_payload`)

When calling `gemini-4-argon` on Vertex AI `generateContent` / `streamGenerateContent` [^src-model-router]:
1. **Forbidden Legacy Fields**: Strip `thinkingBudget` (both top-level `generationConfig.thinkingBudget` and nested `thinkingConfig.thinkingBudget`), `candidateCount`, `frequencyPenalty`, and `presencePenalty` to prevent HTTP `400 INVALID_ARGUMENT`.
2. **Thinking Level Normalization**: Use `generationConfig.thinkingConfig.thinkingLevel` with values `"LOW"`, `"MEDIUM"`, or `"HIGH"`. Normalize `"MINIMAL"` $\rightarrow$ `"MEDIUM"` and `"MAX"` / `"XHIGH"` $\rightarrow$ `"HIGH"`.

[^src-model-router]: Verified in `src/ccpa_mock.py` (`v3.9.0`).
[^src-deprecated-guard]: Verified in `src/hooks/rules/deprecated_models.py` (`v3.9.0`).
