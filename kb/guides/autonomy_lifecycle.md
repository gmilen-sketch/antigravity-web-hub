---
okf_version: "0.2"
id: autonomy-lifecycle-governance
title: "Autonomous Governance, Dual-Mode Harness, 2-Stage Goldfish-Judge Gate & 20 PD-Q Skills"
summary: "Self-documentation for the 4 lifecycle hooks (PreInvocation, PostInvocation, PreToolUse, Stop), 14 Wave-12 clean-room kernels (AGW-W12-01..14), P0/P1 circuit-breakers, 20 PD-Q skills, 5 custom subagents, and turnkey A/B benchmark runner."
type: guide
status: verified
confidence: 0.99
last_verified: "2026-11-09"
tags: [black-hat, goldfish, judge, pre-invocation, sentinel, dreaming, okf, pd-q, benchmark]
aliases: [black-hat-gate, goldfish-judge, dreaming-engine, p0-engine, p1-engine, sentinel-dispatch, dual-mode-classifier]
related_concepts: [antigravity-web-hub-architecture, gemini-models-and-vertex-api, antigravity-cli-and-sdk, google-adk-and-a2a-protocol]
sources:
  - id: src-pre-hook
    type: code_repo
    title: "src/hooks/kg_pre_invocation_hook.py — Dual-Mode Classifier, Turn-0 KV Guard & IDF Grounding"
    URI: "src/hooks/kg_pre_invocation_hook.py"
    fetched_at: "2026-11-09"
  - id: src-sentinel
    type: code_repo
    title: "src/hooks/sentinel_dispatch.py — PreToolUse Sentinel & Heredoc/VCS Guards"
    URI: "src/hooks/sentinel_dispatch.py"
    fetched_at: "2026-11-09"
  - id: src-stop-gate
    type: code_repo
    title: "src/hooks/agent_stop_black_hat_gate.py — 2-Stage Goldfish -> Judge Stop Gate v4.18"
    URI: "src/hooks/agent_stop_black_hat_gate.py"
    fetched_at: "2026-11-09"
---

# Autonomous Governance, Dual-Mode Harness, 2-Stage Goldfish-Judge Gate & 20 PD-Q Skills

## 1. Four Deterministic Lifecycle Hooks (`hooks.json` + `run_hook_safe.sh`)

Antigravity Web Hub (`v3.9.0`) governs every agent turn through four deterministic hooks (`PreInvocation`, `PostInvocation`, `PreToolUse`, `Stop`) registered in `hooks.json` [^src-pre-hook] [^src-sentinel] [^src-stop-gate]:

1. **`PreInvocation` (`src/hooks/kg_pre_invocation_hook.py`)**:
   - **Dual-Mode Execution Classifier (`classify_execution_mode`, `AGW-W12-01`)**: Automatically detects `SWE_BENCHMARK_MODE` (`/testbed`, `/workspace`, `/swebench`, `/harbor`, `AGW_EXECUTION_MODE=SWE_BENCHMARK_MODE`) vs `PORTFOLIO_MODE`, injecting the compact 4-rule `UNIVERSAL_SWE_KERNEL` during coding benchmarks so prose formatting rules never interfere with repository test graders [^src-pre-hook].
   - **Turn-0 Frozen KV-Cache Guard (`should_inject_turn0_kernel`, `AGW-W12-02`) & Strict Schema Sanitizer (`enforce_strict_pre_invocation_schema`, `AGW-W12-03`)**: Preserves prompt prefix KV-cache hit rates across multi-turn trajectories and emits strictly `{"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]}` (`HookSystemMessage`) [^src-pre-hook].
   - **Sub-Millisecond IDF & 2-Hop KG Grounding (`resolve_hybrid_entities_idf`, `AGW-W12-09`)**: Strips `<CONTEXT_SUMMARY>` and `<SYSTEM_MESSAGE>` noise and resolves canonical entities + Top-3 `okf:*` dossiers from `/dev/shm/agw_kg_warm_cache.json` [^src-pre-hook].
2. **`PreToolUse` (`src/hooks/sentinel_dispatch.py`)**:
   - Enforces modular safety rules (`r31_hook_integrity_guard.py`, `destructive_commands.py`, `deprecated_models.py`, `file_bounds.py`, `rule_11_anonymization.py`, `zero_latex.py`) plus `rewrite_inline_python_c_to_heredoc` (`AGW-W12-05`), `check_sandbox_and_own_cid_boundary` (`AGW-W12-06`), `check_reactive_wakeup_polling_guard` (`AGW-W12-07`), and `enforce_non_interactive_vcs_flags` (`AGW-W12-14`) [^src-sentinel].
3. **`Stop` (`src/hooks/agent_stop_black_hat_gate.py`)**:
   - Enforces the **2-Stage Stateless Goldfish (`black-hat-goldfish`) $\rightarrow$ Isolated Judge (`black-hat-judge`)** verification gate whenever files are mutated, plus zero-`.pyc` in-memory `compile()` validation (`enforce_shebang_exec_and_inmemory_compile`, `AGW-W12-08`) and post-mutation local test proof (`has_post_mutation_local_test_proof`, `AGW-W12-13`) [^src-stop-gate].

## 2. 20 Clean-Room `PD-Q` Skills, 5 Subagents & Turnkey A/B Benchmark Runner

* **20 `PD-Q` Skills (`skills/manifest.json`)**: `antigravity-web-builder`, `black-hat-analysis`, `diagram-renderer`, `finops-focus-auditor`, `first-principles-brainstormer`, `golden-ab-testing`, `idea-evaluator`, `issue-tracker-manager`, `migration-center-architect`, `open-deep-researcher`, `p0-quality-first-engine`, `p1-quality-first-engine`, `parallel-task-orchestrator`, `playwright-agent-browser`, `self-grill`, `six-hats-evaluator`, `universal-solution-architect`, `universal-task-sync`, `workspace-docs-publisher`, and `workspace-slides-generator`.
* **5 Custom Subagents (`agents/`)**: `black-hat-goldfish`, `black-hat-judge`, `black-hat-critic`, `dreaming-improvement-reasoner`, and `workspace-housekeeper`.
* **Turnkey Paired A/B Benchmark Runner (`scripts/run_ab_benchmark.py`)**: Evaluates Vanilla Antigravity (Arm A, `:9080`) vs Customized Antigravity (Arm B, `:9081`) under ceteris-paribus controls (`python3 -B scripts/run_ab_benchmark.py --self-test`, `--mode dual-daemon`, `--mode harbor`).

[^src-pre-hook]: Verified in `src/hooks/kg_pre_invocation_hook.py` (`v3.9.0`).
[^src-sentinel]: Verified in `src/hooks/sentinel_dispatch.py` (`v3.9.0`).
[^src-stop-gate]: Verified in `src/hooks/agent_stop_black_hat_gate.py` (`v4.18`).
