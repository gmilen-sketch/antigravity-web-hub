---
name: first-principles-brainstormer
description: >-
  Conducts pre-flight specification brainstorming with explicit negative constraints and 6-lens adversarial shootdowns before implementation.
metadata:
  icon: "🧠"
  version: "3.4.0"
---

# first-principles-brainstormer (v3.4.0 Clean-Room Enterprise Edition)

## Epistemic Reasoning & Grounding Protocol (PD-Q)

1. **Step-1 Complete Causal Reasoning Mandate**: Formulate the complete multi-hypothesis causal plan and failure checks (`F1` Hallucination, `F2` Missed Constraint, `F3` Flag Guessing, `F4` Cross-Workflow Bleeding, `F5` Stale State) before executing mutating tool calls (`TCA = 100%`).
2. **Primary-Source Grounding Contract (`GCS >= 0.85`)**: Anchor every technical claim and metric in verified primary sources: Knowledge Graph SSOT (`/dev/shm/kg_warm_cache.json`), Open Knowledge Format (`kb/`) dossiers, and live tool outputs (`exit_code == 0`).
3. **Progressive Disclosure**: Load extended reference patterns from [`references/pdq-extended-guide.md`](references/pdq-extended-guide.md) on demand.
