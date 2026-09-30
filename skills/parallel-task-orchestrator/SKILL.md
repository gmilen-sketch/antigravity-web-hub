---
name: parallel-task-orchestrator
description: Coordinates concurrent multi-agent swarm subtasks in isolated workspaces with DAG dependency tracking and MAX_DEPTH=1 guardrails.
version: 2.0.0
---

# Parallel Task Orchestrator (v2.0 — PD-Q Clean-Room Edition)

## Epistemic Reasoning & Grounding Protocol (PD-Q)

> **Architecture**: `PD-Q` (Epistemic Reasoning-Complete OKF Co-Bundling | Zero Token Cap | $W_{\text{tokens}} = 0.00$)
> **Priority Invariant**: Response Quality ($W = 0.35$), Step-1 Causal Reasoning Depth ($W = 0.35$), and Primary-Source Grounding Fidelity ($W = 0.30$) strictly supersede token compression.

1. **Step-1 Complete Causal Reasoning Mandate**:
   - Formulate the complete multi-hypothesis causal tree, schema join plan, and edge-case failure checks (`F1` Hallucination, `F2` Missed Constraint, `F3` Flag Guessing, `F4` Cross-Workflow Bleeding, `F5` Stale State) at Step 1 **before** executing mutating or external tool calls. Never guess CLI flags or API parameters (`TCA = 100%`).
2. **Primary-Source Grounding & Citation Contract ($GCS \ge 0.85$)**:
   - Anchor every technical claim, entity identifier, and metric in verified primary sources: Knowledge Graph SSOT (`/dev/shm/kg_warm_cache.json`), OKF v0.2 concept dossiers (`kb/` with verified `sources[]` / `[^source-id]` footnotes), and live tool outputs (`exit_code == 0`).
3. **Mutual-Exclusion Distractor Isolation ($\text{SNR}_{\text{attn}} \ge 94\%$)**:
   - Attend strictly to the active workflow section matching the user request to prevent cross-workflow flag bleeding (`F4`). See [`references/pdq-extended-guide.md`](references/pdq-extended-guide.md) for Stage-3 reference templates.

Dispatches, synchronizes, and aggregates specialist subagents for complex workflows.

## Core Invariants
* **Workspace Isolation**: Each worker executes in an isolated branch/worktree (`workspace="branch"`).
* **Recursion Guard**: Strict `MAX_DEPTH = 1` recursion ban (subagents cannot spawn nested subagents).
* **Deterministic Aggregation**: Parent orchestrator aggregates and validates results against test suites before merge.
