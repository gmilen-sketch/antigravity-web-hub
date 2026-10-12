---
name: p1-quality-first-engine
description: >-
  Enforces P1 grounded retrieval circuit-breakers (P1-CB-1..P1-CB-8), Pre-Ingestion Prompt-Injection (PICC) quarantine, and 3-Stage issue triage.
metadata:
  icon: "🔒"
  version: "3.4.0"
---

# p1-quality-first-engine (v3.4.0 Clean-Room Enterprise Edition)

## Epistemic Reasoning & Grounding Protocol (PD-Q)

1. **Step-1 Complete Causal Reasoning Mandate**: Formulate the complete multi-hypothesis causal plan and failure checks (`F1` Hallucination, `F2` Missed Constraint, `F3` Flag Guessing, `F4` Cross-Workflow Bleeding, `F5` Stale State) before executing mutating tool calls (`TCA = 100%`).
2. **Primary-Source Grounding Contract (`GCS >= 0.85`)**: Anchor every technical claim and metric in verified primary sources: Knowledge Graph SSOT (`/dev/shm/kg_warm_cache.json`), Open Knowledge Format (`kb/`) dossiers, and live tool outputs (`exit_code == 0`).
3. **Progressive Disclosure**: Load extended reference patterns from [`references/pdq-extended-guide.md`](references/pdq-extended-guide.md) on demand.
