# Enterprise Agentic Execution & Autonomy Rules (Clean-Room Edition)

## 1. Epistemic Grounding & Bitemporal Knowledge Graph SSOT
- **Knowledge Graph Single Source of Truth (SSOT)**: Query the Bitemporal Knowledge Graph (`~/.gemini/antigravity/knowledge_graph.json` / `/dev/shm/kg_warm_cache.json`) and Open Knowledge Format (`kb/`) dossiers first; verified graph properties supersede local guesses.
- **Lossless Additive Quality Invariant ($I(B^+) \supseteq I(A)$)**: Maintain 100.0% primary evidence fidelity (`GCS >= 0.85`). Never prune primary tool outputs or logs lossily.
- **Step-1 Complete Causal Reasoning (`PD-Q`, $W_{\text{tokens}} = 0.00$)**: Formulate the complete causal tree, schema join plan, and failure checks (`F1` Hallucination, `F2` Missed Constraint, `F3` Flag Guessing, `F4` Cross-Workflow Bleeding, `F5` Stale State) before mutating state.
- **Sentinel File-View Mandate**: Read a skill's `SKILL.md` before executing its CLI scripts or modifying its files.

## 2. Hardened P0 & P1 Quality-First Circuit-Breakers
- **P0 Circuit-Breakers (`p0_quality_first_engine.py`)**: Enforce `CB-1` (`REQUIRED_PRIMARY` vs `OPTIONAL_SECONDARY`), `CB-2` (`exit_code == 0` + required columns), `CB-3` (`12h` intraday lesson cache), `CB-4` (`PD-Q` + Top-3 `okf:*` co-bundling), `CB-5` (`SHA-256` lossless log pointer), `CB-6` (Sub-110ms Mode A/B dispatcher), and `CB-7` (`--self-test` parity).
- **P1 Circuit-Breakers (`p1_quality_first_engine.py`)**: Enforce `P1-CB-1` (2-Pass Grounded Retrieval), `P1-CB-2` (deterministic JSON AST repair), `P1-CB-3` (Single-Pass Regex Prompt Assembly + Anonymization), `P1-CB-4` (`> 168h` drift guard), `P1-CB-5` (3-Stage Issue Triage), and `P1-CB-8` (PICC Prompt-Injection scanner).

## 3. 2-Stage Black-Hat Completion Gate (`black-hat-goldfish` -> `black-hat-judge`)
Before concluding any turn that mutates files or infrastructure (`mutations > 0`):
1. **Stage 1 (`black-hat-goldfish` — Stateless Investigator)**: Invoke `black-hat-goldfish` with a **claims-only** prompt (itemized claims, target paths, verification commands; zero narrative excuses). Wait for `FORENSIC_EVIDENCE_DOSSIER` (`DISCREPANCY_COUNT: 0`).
2. **Stage 2 (`black-hat-judge` — Isolated Adjudicator)**: Invoke `black-hat-judge` with the goldfish `conversationId`, transcript path, claims, and deliverable paths. Require `CRITIC_VERDICT: APPROVED`.
3. **Stage 3 (Bottom-Up Summary & `### ⚡ TL;DR`)**: Conclude with `### 📋 Summary of Approved Response & Deliverables`, `### ⚡ TL;DR` (`<= 80` words), and `CRITIC_VERDICT: APPROVED | GCS = 1.000 | <N/N Checks Passed>`.
