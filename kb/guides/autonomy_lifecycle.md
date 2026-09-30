---
okf_version: "0.2"
id: autonomy-lifecycle-governance
title: "Autonomous Governance, 2-Stage Goldfish-Judge Gate & P0/P1 Engines"
summary: "Turn-0 PreInvocation KV-cache grounding, PreToolUse Sentinel dispatch, 2-Stage Stateless Goldfish -> Isolated Judge Stop gate (v4.3), and Nightly Dreaming v5.2."
type: guide
status: verified
confidence: 0.99
last_verified: "2026-09-30"
tags: [black-hat, goldfish, judge, pre-invocation, dreaming, okf, pd-q]
aliases: [black-hat-gate, goldfish-judge, dreaming-engine, p0-engine, p1-engine]
related_concepts: [antigravity-web-hub-architecture]
sources:
  - id: src-stop-gate
    type: code_repo
    title: "src/hooks/agent_stop_black_hat_gate.py — 2-Stage Goldfish -> Judge Stop Gate v4.3"
    URI: "src/hooks/agent_stop_black_hat_gate.py"
    fetched_at: "2026-09-30"
  - id: src-pre-hook
    type: code_repo
    title: "src/hooks/kg_pre_invocation_hook.py — Turn-1 Pinned KV-Cache & OKF Co-Bundler v3.3"
    URI: "src/hooks/kg_pre_invocation_hook.py"
    fetched_at: "2026-09-30"
---

# Autonomous Governance, 2-Stage Goldfish-Judge Gate & P0/P1 Engines

## Summary

Antigravity Web Hub `v3.3.0` enforces a three-hook autonomous quality lifecycle (`PreInvocation`, `PreToolUse`, and `Stop`) backed by the P0 (`CB-1..CB-7`) and P1 (`P1-CB-1..P1-CB-7`) quality engines and Nightly Dreaming `v5.2` [^src-stop-gate] [^src-pre-hook].

## Core Governance Contracts

1. **Turn-1 Pinned KV-Cache `PreInvocation` Hook (`kg_pre_invocation_hook.py` v3.3)**:
   - Strips `<CONTEXT_SUMMARY>` before lexical matching so historical entities never pollute active turn retrieval [^src-pre-hook].
   - Co-bundles Top-3 `okf:*` concept dossiers alongside 1-hop associative Knowledge Graph neighbors when relevance `score >= 45` [^src-pre-hook].
2. **PreToolUse Sentinel Dispatcher (`sentinel_dispatch.py`)**:
   - Enforces modular guardrails (`destructive_commands.py`, `deprecated_models.py`, `file_bounds.py`, `rule_11_anonymization.py`) prior to shell or file mutations.
3. **2-Stage Stateless Goldfish $\rightarrow$ Isolated Judge `Stop` Gate (`agent_stop_black_hat_gate.py` v4.3)**:
   - Audits `C1–C8` contracts (`black-hat-goldfish` $\rightarrow$ `black-hat-judge`, with single-stage `black-hat-critic` compatibility and in-process attached verification fallback) [^src-stop-gate].

[^src-stop-gate]: Verified in `src/hooks/agent_stop_black_hat_gate.py` (`v4.3`).
[^src-pre-hook]: Verified in `src/hooks/kg_pre_invocation_hook.py` (`v3.3`).
