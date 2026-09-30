---
name: diagram-renderer
description: Compiles and renders Mermaid, GCP Draw DSL, Graphviz, and BENTO architecture diagrams directly to high-resolution PNG/SVG with strict container bounds.
version: 2.0.0
---

# Diagram Renderer (v15.2 — BENTO Clean-Room Edition)

## Epistemic Reasoning & Grounding Protocol (PD-Q)

> **Architecture**: `PD-Q` (Epistemic Reasoning-Complete OKF Co-Bundling | Zero Token Cap | $W_{\text{tokens}} = 0.00$)
> **Priority Invariant**: Response Quality ($W = 0.35$), Step-1 Causal Reasoning Depth ($W = 0.35$), and Primary-Source Grounding Fidelity ($W = 0.30$) strictly supersede token compression.

1. **Step-1 Complete Causal Reasoning Mandate**:
   - Formulate the complete multi-hypothesis causal tree, schema join plan, and edge-case failure checks (`F1` Hallucination, `F2` Missed Constraint, `F3` Flag Guessing, `F4` Cross-Workflow Bleeding, `F5` Stale State) at Step 1 **before** executing mutating or external tool calls. Never guess CLI flags or API parameters (`TCA = 100%`).
2. **Primary-Source Grounding & Citation Contract ($GCS \ge 0.85$)**:
   - Anchor every technical claim, entity identifier, and metric in verified primary sources: Knowledge Graph SSOT (`/dev/shm/kg_warm_cache.json`), OKF v0.2 concept dossiers (`kb/` with verified `sources[]` / `[^source-id]` footnotes), and live tool outputs (`exit_code == 0`).
3. **Mutual-Exclusion Distractor Isolation ($\text{SNR}_{\text{attn}} \ge 94\%$)**:
   - Attend strictly to the active workflow section matching the user request to prevent cross-workflow flag bleeding (`F4`). See [`references/pdq-extended-guide.md`](references/pdq-extended-guide.md) for Stage-3 reference templates.

Compiles text-based architecture and topology diagrams to high-resolution PNG/SVG vector assets using BENTO 6-tier semantic styling and strict 840px/1280px/1600px container bounds.

## Supported Engines
* **Mermaid.js (`render_mermaid.py`)**: Flowcharts, Sequence Diagrams, State Machines, C4 Contexts (`840px` width, `zoom: 1.0`, `--height 8000`).
* **GCP Draw BENTO (`render_gcp_draw.py`)**: Cloud architecture topology diagrams with sentence-case naming and A4 landscape layout (`-right->`, `-down->`).
* **Graphviz DOT / PlantUML**: Complex directed graphs and component protocols.

## Usage
```bash
python3 src/diagram_renderer/render_mermaid.py
python3 src/diagram_renderer/render_gcp_draw.py -o /tmp/gcp-architecture.svg
```
