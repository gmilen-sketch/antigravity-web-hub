---
name: open-deep-researcher
description: Conducts multi-source deep research swarms across open web, arXiv, PubMed, GitHub, and OKF v0.2 knowledge bases using the 6-stage Elephant-Goldfish Model (EGM).
version: 2.0.0
---

# Open Deep Researcher (v2.0 — EGM + OKF v0.2 Edition)

## Epistemic Reasoning & Grounding Protocol (PD-Q)

> **Architecture**: `PD-Q` (Epistemic Reasoning-Complete OKF Co-Bundling | Zero Token Cap | $W_{\text{tokens}} = 0.00$)
> **Priority Invariant**: Response Quality ($W = 0.35$), Step-1 Causal Reasoning Depth ($W = 0.35$), and Primary-Source Grounding Fidelity ($W = 0.30$) strictly supersede token compression.

1. **Step-1 Complete Causal Reasoning Mandate**:
   - Formulate the complete multi-hypothesis causal tree, schema join plan, and edge-case failure checks (`F1` Hallucination, `F2` Missed Constraint, `F3` Flag Guessing, `F4` Cross-Workflow Bleeding, `F5` Stale State) at Step 1 **before** executing mutating or external tool calls. Never guess CLI flags or API parameters (`TCA = 100%`).
2. **Primary-Source Grounding & Citation Contract ($GCS \ge 0.85$)**:
   - Anchor every technical claim, entity identifier, and metric in verified primary sources: Knowledge Graph SSOT (`/dev/shm/kg_warm_cache.json`), OKF v0.2 concept dossiers (`kb/` with verified `sources[]` / `[^source-id]` footnotes), and live tool outputs (`exit_code == 0`).
3. **Mutual-Exclusion Distractor Isolation ($\text{SNR}_{\text{attn}} \ge 94\%$)**:
   - Attend strictly to the active workflow section matching the user request to prevent cross-workflow flag bleeding (`F4`). See [`references/pdq-extended-guide.md`](references/pdq-extended-guide.md) for Stage-3 reference templates.

Autonomous deep research agent leveraging open web search engines, OKF v0.2 dossiers (`kb/`), and local embeddings.

## 6-Stage EGM Pipeline
1. **Stage 1 (Query Decomposition & Intent Expansion)**: Break prompt into orthogonal search facets.
2. **Stage 2 (Multi-Source Retrieval)**: Query primary code/docs, OKF v0.2 `kb/`, arXiv, GitHub Search, and DuckDuckGo.
3. **Stage 3 (Epistemic Source Verification)**: Score sources (Official Docs: 1.0 > Academic: 0.9 > Community: 0.6).
4. **Stage 4 (Six Hats Perspective Evaluation)**: Pressure-test findings across 6 cognitive dimensions.
5. **Stage 5 (Cross-Source Fact Synthesis)**: Reconcile discrepancies and build citation-verified fact matrices.
6. **Stage 6 (Structured Citation Report)**: Generate actionable technical reports with `[^source-id]` footnotes.
