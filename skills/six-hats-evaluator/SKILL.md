---
name: six-hats-evaluator
description: Executes structured 360-degree decision matrix evaluations and adversarial Goldfish shootdowns using Edward de Bono's Six Thinking Hats framework.
version: 2.0.0
---

# Six Thinking Hats Evaluator (v2.0 — EGM Pre-Flight & Shootdown Edition)

## Epistemic Reasoning & Grounding Protocol (PD-Q)

> **Architecture**: `PD-Q` (Epistemic Reasoning-Complete OKF Co-Bundling | Zero Token Cap | $W_{\text{tokens}} = 0.00$)
> **Priority Invariant**: Response Quality ($W = 0.35$), Step-1 Causal Reasoning Depth ($W = 0.35$), and Primary-Source Grounding Fidelity ($W = 0.30$) strictly supersede token compression.

1. **Step-1 Complete Causal Reasoning Mandate**:
   - Formulate the complete multi-hypothesis causal tree, schema join plan, and edge-case failure checks (`F1` Hallucination, `F2` Missed Constraint, `F3` Flag Guessing, `F4` Cross-Workflow Bleeding, `F5` Stale State) at Step 1 **before** executing mutating or external tool calls. Never guess CLI flags or API parameters (`TCA = 100%`).
2. **Primary-Source Grounding & Citation Contract ($GCS \ge 0.85$)**:
   - Anchor every technical claim, entity identifier, and metric in verified primary sources: Knowledge Graph SSOT (`/dev/shm/kg_warm_cache.json`), OKF v0.2 concept dossiers (`kb/` with verified `sources[]` / `[^source-id]` footnotes), and live tool outputs (`exit_code == 0`).
3. **Mutual-Exclusion Distractor Isolation ($\text{SNR}_{\text{attn}} \ge 94\%$)**:
   - Attend strictly to the active workflow section matching the user request to prevent cross-workflow flag bleeding (`F4`). See [`references/pdq-extended-guide.md`](references/pdq-extended-guide.md) for Stage-3 reference templates.

Pressure-tests architectural, technical, and business decisions across 6 cognitive dimensions:

1. ⚪ **White Hat (Facts & Telemetry)**: Objective metrics, system constraints, verified primary telemetry.
2. 🟡 **Yellow Hat (Value Multipliers & ROI)**: Upside potential, speedup factors, cost savings.
3. ⚫ **Black Hat (Risks & Critical Failure Modes)**: Vulnerabilities, security risks, regressions, falsification tests.
4. 🔴 **Red Hat (Developer Experience & Intuition)**: User sentiment, ergonomic friction, flow state.
5. 🟢 **Green Hat (Lateral Innovation & Alternatives)**: Out-of-the-box solutions, clean refactors.
6. 🔵 **Blue Hat (Executive Synthesis & Action Plan)**: Weighted decision matrix verdict, gates, rollout phases.
