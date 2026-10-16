---
name: parallel-task-orchestrator
description: >-
  Coordinates parallel leaf subagents (MAX_DEPTH=1) with <hydrated_context> XML bundles and disjoint write-set enforcement.
metadata:
  icon: "🐝"
  version: "3.4.0"
---

# parallel-task-orchestrator (v3.4.0 Clean-Room Enterprise Edition)

## Epistemic Reasoning & Grounding Protocol (PD-Q)

1. **Step-1 Complete Causal Reasoning Mandate**: Formulate the complete multi-hypothesis causal plan and failure checks (`F1` Hallucination, `F2` Missed Constraint, `F3` Flag Guessing, `F4` Cross-Workflow Bleeding, `F5` Stale State) before executing mutating tool calls (`TCA = 100%`).
2. **Primary-Source Grounding Contract (`GCS >= 0.85`)**: Anchor every technical claim and metric in verified primary sources: Knowledge Graph SSOT (`/dev/shm/kg_warm_cache.json`), Open Knowledge Format (`kb/`) dossiers, and live tool outputs (`exit_code == 0`).
3. **Progressive Disclosure**: Load extended reference patterns from [`references/pdq-extended-guide.md`](references/pdq-extended-guide.md) on demand.


## Native Agent Swarm (`/swarm`) & Dynamic Python Workflows (`run_workflow`)

1. **Native Multi-Agent Swarm (`/swarm`)**:
   - Spawn parallel workers on a shared board (`board.jsonl`, `members.json`) via `swarm(action="add", name="worker", workspace="share", brief="...")`.
   - Workers may spawn bounded helper sub-workers (`swarm(action="add")`) and coordinate with a 3-minute `swarm_monitor` watchdog.
2. **Dynamic Python Orchestration (`run_workflow`)**:
   - Fan out over independent modules or staged pipelines using `from advanced import parallel, agent, race, retry, fallback, best_of, verify`.
   - Enforce Bernstein disjoint write-set verification (`W_i ∩ W_j = ∅`, `R_i ∩ W_j = ∅`) before merging parallel worker outputs.
