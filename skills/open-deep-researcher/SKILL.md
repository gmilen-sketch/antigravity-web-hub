---
name: open-deep-researcher
description: Conducts multi-source deep research swarms across open web, arXiv, PubMed, GitHub, and enterprise vector stores using the 6-stage Elephant-Goldfish Model (EGM).
version: 1.0.0
---

# Open Deep Researcher (Clean-Room Edition)

Autonomous deep research agent leveraging open web search engines and local embeddings.

## 6-Stage EGM Pipeline
1. **Stage 1 (Query Decomposition & Intent Expansion)**: Break prompt into orthogonal search facets.
2. **Stage 2 (Multi-Source Retrieval)**: Query Tavily, DuckDuckGo, arXiv, GitHub Search.
3. **Stage 3 (Epistemic Source Verification)**: Score sources (Official Docs: 1.0 > Academic: 0.9 > Community: 0.6).
4. **Stage 4 (Six Hats Perspective Evaluation)**: Pressure-test findings across 6 dimensions.
5. **Stage 5 (Cross-Source Fact Synthesis)**: Reconcile discrepancies and build fact matrices.
6. **Stage 6 (Structured Citation Report)**: Generate actionable technical reports with verified URLs.
