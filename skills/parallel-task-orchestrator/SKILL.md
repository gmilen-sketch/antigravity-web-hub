---
name: parallel-task-orchestrator
description: Coordinates concurrent multi-agent swarm subtasks in isolated workspaces with DAG dependency tracking.
version: 1.0.0
---

# Parallel Task Orchestrator (Clean-Room Edition)

Dispatches, synchronizes, and aggregates specialist subagents for complex workflows.

## Core Invariants
* **Workspace Isolation**: Each worker executes in an isolated branch/worktree (`workspace="branch"`).
* **Recursion Guard**: Strict `MAX_DEPTH = 1` recursion ban (subagents cannot spawn nested subagents).
* **Deterministic Aggregation**: Parent orchestrator aggregates and validates results against test suites before merge.
