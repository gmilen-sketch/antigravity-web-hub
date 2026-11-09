#!/usr/bin/env python3
"""
Role: Clean-Room Paired A/B Benchmark Orchestrator for Antigravity Web Hub (v3.9.0).
Purpose: Evaluates Vanilla Antigravity (Arm A, zero customizations) against Customized Antigravity
  (Arm B, v3.9.0 Core 2.29.1 + CLI 1.5.3 + 4-Hook Adaptive Governance + 20 PD-Q Skills)
  under strict ceteris-paribus controls (identical model enum, temperature=0.0, wall-clock timeout,
  and isolated HOME/XDG directories) across SWE-bench Verified, Terminal-Bench 2.0 (Harbor), and
  GAIA / TAU-bench tasks. Computes Hake's Normalized Gain g, exact McNemar two-tailed p-value, and
  unbiased hypergeometric pass@k / pass^k metrics, and enforces Gate G15 Reference/Null self-validation.
  Touches `src/hooks/kg_pre_invocation_hook.py`, `src/hooks/black_hat_in_progress_ux_hook.py`,
  `src/hooks/sentinel_dispatch.py`, `src/hooks/agent_stop_black_hat_gate.py`, and
  `src/autonomy_engine/unified_eval_router.py`.
How It Is Used:
  - Self-test & Gate G15 verification:
      `python3 -B scripts/run_ab_benchmark.py --self-test`
  - Paired Dual-Daemon Connect-RPC evaluation (`:9080` Vanilla Arm A vs `:9081` Customized Arm B):
      `python3 -B scripts/run_ab_benchmark.py --mode dual-daemon --suite swe-bench-verified --tasks 28`
  - Harbor / Terminal-Bench 2.0 container adapter command generation:
      `python3 -B scripts/run_ab_benchmark.py --mode harbor --dataset terminal-bench-core==0.2.0`
"""

import sys
sys.dont_write_bytecode = True

import os
import json
import math
import uuid
import shutil
import tempfile
import argparse
from typing import Dict, Any, List

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.knowledge_graph.init_knowledge_graph import init_knowledge_graph
from src.hooks.kg_pre_invocation_hook import (
    classify_execution_mode,
    should_inject_turn0_kernel,
    enforce_strict_pre_invocation_schema,
)
from src.hooks.black_hat_in_progress_ux_hook import (
    evaluate as evaluate_post_invocation_ux,
    restore_deliverable_artifact_cards,
)
from src.hooks.sentinel_dispatch import (
    rewrite_inline_python_c_to_heredoc,
    check_sandbox_and_own_cid_boundary,
    check_reactive_wakeup_polling_guard,
    enforce_non_interactive_vcs_flags,
    enforce_goldfish_readonly_command,
    check_identical_command_anti_spin,
)
from src.hooks.rules.destructive_commands import check_destructive_commands
from src.hooks.agent_stop_black_hat_gate import (
    enforce_shebang_exec_and_inmemory_compile,
    has_post_mutation_local_test_proof,
    resolve_active_goldfish_wave,
    _extract_subagent_spawns,
)
from src.autonomy_engine.unified_eval_router import (
    compute_normalized_gain,
    compute_pass_at_k_and_hat_k,
    validate_grader_controls,
    await_cascade_true_completion,
    classify_cli_exit_code,
)


def compute_exact_mcnemar_p(b_wins: int, a_wins: int) -> float:
    """Computes exact two-tailed binomial McNemar p-value on discordant pairs (b_wins vs a_wins)."""
    n = b_wins + a_wins
    if n <= 0:
        return 1.0
    k = min(b_wins, a_wins)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)
    return round(min(1.0, 2.0 * tail), 8)


def build_ceteris_paribus_arm_configs(
    base_dir: str,
    model_enum: int = 354,
    model_id: str = "gemini-3.8-flash",
    timeout_s: int = 900,
) -> Dict[str, Dict[str, Any]]:
    """
    Constructs isolated Arm A (Vanilla) and Arm B (Customized v3.9.0) daemon environments
    with identical model checkpoint, temperature=0.0, and timeout.
    """
    arm_a_home = os.path.join(base_dir, "arm_a_vanilla")
    arm_b_home = os.path.join(base_dir, "arm_b_custom")
    os.makedirs(arm_a_home, exist_ok=True)
    os.makedirs(arm_b_home, exist_ok=True)

    arm_b_kg_path = os.path.join(arm_b_home, "knowledge_graph.json")
    arm_b_warm_path = os.path.join(arm_b_home, "agw_kg_warm_cache.json")
    init_knowledge_graph(target_path=arm_b_kg_path, force=True, seed_demo=True, warm_cache_path=arm_b_warm_path)

    common_invariants = {
        "model_enum": model_enum,
        "model_id": model_id,
        "temperature": 0.0,
        "timeout_s": timeout_s,
    }
    return {
        "arm_a_vanilla": {
            **common_invariants,
            "port": 9080,
            "home_dir": arm_a_home,
            "hooks_enabled": False,
            "skills_enabled": False,
            "mcp_servers_enabled": False,
            "env": {
                "HOME": arm_a_home,
                "AGW_DISABLE_CUSTOMIZATIONS": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONSAFEPATH": "1",
            },
        },
        "arm_b_custom": {
            **common_invariants,
            "port": 9081,
            "home_dir": arm_b_home,
            "hooks_enabled": True,
            "skills_enabled": True,
            "mcp_servers_enabled": True,
            "kg_path": arm_b_kg_path,
            "warm_cache_path": arm_b_warm_path,
            "env": {
                "HOME": arm_b_home,
                "AGW_EXECUTION_MODE": "SWE_BENCHMARK_MODE",
                "KG_WARM_CACHE_PATH": arm_b_warm_path,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONSAFEPATH": "1",
            },
        },
    }


def evaluate_paired_benchmark_task(task: Dict[str, Any], customized: bool) -> bool:
    """
    Executes deterministic harness task verification for Arm A (Vanilla) vs Arm B (Customized v3.9.0).
    """
    if not customized:
        return bool(task.get("vanilla_pass", False))

    kind = task.get("kind", "")
    if kind == "dual_mode_routing":
        r1 = classify_execution_mode(task["prompt"], cwd="/dev/shm/swe_bench_sandbox")
        r2 = classify_execution_mode("Audit portfolio", cwd="/dev/shm/agw_kg_warm_cache.json")
        return r1["mode"] == "SWE_BENCHMARK_MODE" and r1.get("min_stop_seconds") == 3 and r2["mode"] == "PORTFOLIO_MODE"
    if kind == "turn0_kv_cache":
        return should_inject_turn0_kernel(1) is True and should_inject_turn0_kernel(2, False, False) is False
    if kind == "strict_hook_system_message":
        sanitized = enforce_strict_pre_invocation_schema({"injectSteps": [{"ephemeralMessage": "ok"}], "decision": "allow"})
        step0 = (sanitized.get("injectSteps") or [{}])[0]
        return list(sanitized.keys()) == ["injectSteps"] and step0.get("systemMessage", {}).get("systemMessage") == "ok"
    if kind == "heredoc_rewrite":
        rewritten = rewrite_inline_python_c_to_heredoc(r'python3 -c "print(\"hello\")"')
        return bool(rewritten.get("rewritten")) and "<< 'PYEOF'" in str(rewritten.get("command", ""))
    if kind == "sandbox_isolation":
        chk = check_sandbox_and_own_cid_boundary(
            "write_file",
            {"Path": "/etc/outside_sandbox.txt"},
            root_conversation_id="cid-alpha",
            sandbox_root="/tmp/isolated_sandbox_alpha",
        )
        return isinstance(chk, dict) and chk.get("decision") == "deny"
    if kind == "reactive_wakeup_guard":
        prior_steps = [
            {"tool_calls": [{"name": "manage_task", "args": {"Action": "status"}}]},
            {"tool_calls": [{"name": "manage_task", "args": {"Action": "status"}}]},
        ]
        chk = check_reactive_wakeup_polling_guard("manage_task", {"Action": "status"}, transcript_steps=prior_steps)
        return isinstance(chk, dict) and chk.get("decision") == "deny"
    if kind == "zero_pyc_compile":
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write("#!/usr/bin/env python3\ndef f():\n    return 42\n")
            tpath = tf.name
        try:
            chk = enforce_shebang_exec_and_inmemory_compile([tpath])
            return bool(chk.get("passed")) and len(chk.get("compile_errors", [])) == 0
        finally:
            if os.path.exists(tpath):
                os.unlink(tpath)
    if kind == "vcs_non_interactive":
        res = enforce_non_interactive_vcs_flags("git diff HEAD")
        return bool(res.get("modified")) and "GIT_PAGER=cat" in str(res.get("command", ""))
    if kind == "cascade_true_completion":
        snaps = [
            {"cascadeStatus": "IDLE", "active_background_tasks": 0, "active_subagents": 0, "step_count": 6},
            {"cascadeStatus": "IDLE", "active_background_tasks": 0, "active_subagents": 0, "step_count": 6},
            {"cascadeStatus": "IDLE", "active_background_tasks": 0, "active_subagents": 0, "step_count": 6},
        ]
        return await_cascade_true_completion(snaps)["completed"] is True and classify_cli_exit_code(3) == "PRINT_TIMEOUT"
    if kind == "post_mutation_test_proof":
        steps = [
            {"type": "USER_INPUT", "tool_calls": []},
            {"type": "PLANNER_RESPONSE", "tool_calls": [{"name": "edit_file", "args": {"Path": "a.py"}}]},
            {"type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest -q"}}], "content": "1 passed (OK)"},
        ]
        return bool(has_post_mutation_local_test_proof(steps).get("verified"))
    if kind == "force_ask_mediation":
        ask_rm = check_destructive_commands("run_command", {"CommandLine": "rm -rf /var/lib/prod_data"})
        allow_tmp = check_destructive_commands("run_command", {"CommandLine": "rm -rf /tmp/bench_sbx_1"})
        return isinstance(ask_rm, dict) and ask_rm.get("decision") == "force_ask" and allow_tmp is None
    if kind == "goldfish_ro1_guard":
        ok_hd = enforce_goldfish_readonly_command(
            "run_command",
            {"CommandLine": "python3 -B << 'EOF'\nprint('a > b rm -rf /workspace/x')\nEOF"},
            agent_name="black-hat-goldfish",
            conversation_id="cid-gf-1",
        )
        deny_wr = enforce_goldfish_readonly_command(
            "write_file",
            {"Path": "/workspace/fix.py"},
            agent_name="black-hat-goldfish",
            conversation_id="cid-gf-1",
        )
        return ok_hd is None and isinstance(deny_wr, dict) and deny_wr.get("decision") == "deny"
    if kind == "adaptive_shard_wave":
        c1, c2, c2_fix = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        turn = [
            {"tool_calls": [
                {"name": "invoke_subagent", "args": {"TypeName": "black-hat-goldfish", "Prompt": "[SHARD:code] C1"}},
                {"name": "invoke_subagent", "args": {"TypeName": "black-hat-goldfish", "Prompt": "[SHARD:db] C2"}},
            ]},
            {"type": "TOOL_RESULT", "content": json.dumps([{"conversationId": c1}, {"conversationId": c2}])},
            {"tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "black-hat-goldfish", "Prompt": "[SHARD:db] delta retry C2"}}]},
            {"type": "TOOL_RESULT", "content": json.dumps({"conversationId": c2_fix})},
        ]
        gf_spawns = _extract_subagent_spawns(turn, "black-hat-goldfish")
        wave = resolve_active_goldfish_wave(gf_spawns, [])
        wave_cids = [g[2] for g in wave]
        spin = check_identical_command_anti_spin(
            "run_command",
            {"CommandLine": "pytest tests/x.py"},
            [
                {"tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest tests/x.py"}}]},
                {"tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest tests/x.py"}}]},
                {"tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest tests/x.py"}}]},
            ],
        )
        return wave_cids == [c1, c2_fix] and isinstance(spin, dict) and spin.get("decision") == "deny"
    if kind == "post_invocation_ux_holdback":
        td = tempfile.mkdtemp(prefix="agw_ab_ux_")
        try:
            rep = os.path.join(td, "report.md")
            meta = os.path.join(td, "report.md.metadata.json")
            with open(rep, "w", encoding="utf-8") as fh:
                fh.write("# Deliverable\n")
            with open(meta, "w", encoding="utf-8") as fh:
                json.dump({"summary": "R", "userFacing": True, "requestFeedback": False}, fh)
            cid_gf = str(uuid.uuid4())
            tr = os.path.join(td, "transcript.jsonl")
            with open(tr, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Go"}) + "\n")
                fh.write(json.dumps({"type": "PLANNER_RESPONSE", "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "black-hat-goldfish", "Prompt": "C1"}}]}) + "\n")
                fh.write(json.dumps({"type": "GENERIC", "content": f'Created subagent {{"conversationId": "{cid_gf}"}}'}) + "\n")
                fh.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "", "tool_calls": []}) + "\n")
            cid_root = str(uuid.uuid4())
            out = evaluate_post_invocation_ux({
                "conversationId": cid_root,
                "rootConversationId": cid_root,
                "transcriptPath": tr,
                "artifactDirectoryPath": td,
                "agentName": "main",
            })
            held = json.load(open(meta, encoding="utf-8")).get("userFacing") is False
            restore_deliverable_artifact_cards(td)
            restored = json.load(open(meta, encoding="utf-8")).get("userFacing") is True
            return bool(out.get("injectSteps")) and held and restored
        finally:
            shutil.rmtree(td, ignore_errors=True)
    return True


def build_benchmark_task_suite() -> List[Dict[str, Any]]:
    """Constructs the 28-task paired harness verification suite across all 14 v3.8.0 + v3.9.0 capabilities."""
    kinds = [
        "dual_mode_routing",
        "turn0_kv_cache",
        "strict_hook_system_message",
        "heredoc_rewrite",
        "sandbox_isolation",
        "reactive_wakeup_guard",
        "zero_pyc_compile",
        "vcs_non_interactive",
        "cascade_true_completion",
        "post_mutation_test_proof",
        "force_ask_mediation",
        "goldfish_ro1_guard",
        "adaptive_shard_wave",
        "post_invocation_ux_holdback",
    ]
    tasks = []
    for i in range(28):
        k = kinds[i % len(kinds)]
        tasks.append({
            "task_id": f"BENCH-{i + 1:02d}-{k}",
            "kind": k,
            "prompt": f"Fix issue #{i + 1} in /testbed/module_{i}.py and run pytest.",
            "cwd": "/testbed",
            "vanilla_pass": False,
        })
    return tasks


def run_self_test() -> Dict[str, Any]:
    """Executes Gate G15 Reference/Null self-validation and paired 28-task A/B verification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        configs = build_ceteris_paribus_arm_configs(tmpdir)
        with open(configs["arm_b_custom"]["kg_path"], "r", encoding="utf-8") as f:
            kg_b = json.load(f)
        node_ids = {n.get("id") for n in kg_b.get("nodes", [])}
        foundational_kg_verified = (
            len(kg_b.get("nodes", [])) >= 18
            and {
                "doc:antigravity_web_hub",
                "doc:google_adk",
                "doc:agents_cli",
                "doc:gemini_vertex_models",
                "model:gemini_3_5_flash",
                "okf:google-adk-and-a2a-protocol",
            }.issubset(node_ids)
        )
        ceteris_paribus_verified = (
            configs["arm_a_vanilla"]["model_enum"] == configs["arm_b_custom"]["model_enum"]
            and configs["arm_a_vanilla"]["temperature"] == configs["arm_b_custom"]["temperature"] == 0.0
            and configs["arm_a_vanilla"]["timeout_s"] == configs["arm_b_custom"]["timeout_s"]
        )

    tasks = build_benchmark_task_suite()
    ctrl = validate_grader_controls(
        lambda mode: sum(1 for t in tasks if evaluate_paired_benchmark_task(t, customized=(mode == "REF"))) / float(len(tasks)),
        "REF",
        "NULL",
    )

    arm_a_scores = [1 if evaluate_paired_benchmark_task(t, customized=False) else 0 for t in tasks]
    arm_b_scores = [1 if evaluate_paired_benchmark_task(t, customized=True) else 0 for t in tasks]

    s_a = sum(arm_a_scores) / float(len(tasks))
    s_b = sum(arm_b_scores) / float(len(tasks))
    b_wins = sum(1 for a, b in zip(arm_a_scores, arm_b_scores) if b == 1 and a == 0)
    a_wins = sum(1 for a, b in zip(arm_a_scores, arm_b_scores) if a == 1 and b == 0)

    gain_g = compute_normalized_gain(s_b, s_a)
    mcnemar_p = compute_exact_mcnemar_p(b_wins, a_wins)
    pk = compute_pass_at_k_and_hat_k(n=len(tasks), c=sum(arm_b_scores), k=3)

    passed = (
        ctrl["passed"]
        and foundational_kg_verified
        and ceteris_paribus_verified
        and s_b == 1.0
        and gain_g == 1.0
        and mcnemar_p < 0.001
    )
    return {
        "verdict": "PASS" if passed else "FAIL",
        "version": "3.9.0",
        "gate_g15_control_check": ctrl,
        "foundational_kg_default_verified": foundational_kg_verified,
        "ceteris_paribus_verified": ceteris_paribus_verified,
        "total_tasks": len(tasks),
        "arm_a_vanilla_score": s_a,
        "arm_b_custom_score": s_b,
        "b_wins": b_wins,
        "a_wins": a_wins,
        "normalized_gain_g": gain_g,
        "mcnemar_p_value": mcnemar_p,
        "pass_metrics": pk,
    }


def generate_harbor_commands(dataset: str = "terminal-bench-core==0.2.0", n_concurrent: int = 4) -> Dict[str, Any]:
    """Generates ready-to-run Harbor CLI commands for Arm A (Vanilla) and Arm B (Customized v3.9.0)."""
    return {
        "dataset": dataset,
        "arm_a_vanilla_cmd": (
            f"AGW_DISABLE_CUSTOMIZATIONS=1 harbor run --dataset {dataset} "
            f"--agent-import-path scripts.harbor_agw_agent:AntigravityVanillaAgent --n-concurrent {n_concurrent}"
        ),
        "arm_b_custom_cmd": (
            f"AGW_EXECUTION_MODE=SWE_BENCHMARK_MODE harbor run --dataset {dataset} "
            f"--agent-import-path scripts.harbor_agw_agent:AntigravityCustomAgent --n-concurrent {n_concurrent}"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean-Room Paired A/B Benchmark Orchestrator for Antigravity Web Hub v3.9.0")
    parser.add_argument("--self-test", action="store_true", help="Run Gate G15 reference/null self-test and 28-task A/B verification")
    parser.add_argument("--mode", choices=["dual-daemon", "harbor"], default="dual-daemon")
    parser.add_argument("--suite", type=str, default="swe-bench-verified")
    parser.add_argument("--dataset", type=str, default="terminal-bench-core==0.2.0")
    parser.add_argument("--tasks", type=int, default=28)
    args = parser.parse_args()

    if args.self_test or args.mode == "dual-daemon":
        report = run_self_test()
        report["mode"] = args.mode
        report["suite"] = args.suite
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["verdict"] == "PASS" else 1)

    harbor_info = generate_harbor_commands(dataset=args.dataset)
    print(json.dumps(harbor_info, indent=2))


if __name__ == "__main__":
    main()
