#!/usr/bin/env python3
"""
Comprehensive Unit & Integration Test Suite for Antigravity Web Hub v3.3.0 Autonomy Upgrades:
- Pillar 1: Knowledge Graph, ACT-R Clamping Floor (A_min = -2.0), OKF v0.2 Compiler & Validator,
  Turn-1 Pinned KV-Cache PreInvocation Hook v3.3 (<CONTEXT_SUMMARY> stripping, score >= 45, 1-hop edges, aliases)
- Pillar 2: Nightly Dreaming v5.2, P0 (CB-1..CB-7) & P1 (P1-CB-1..P1-CB-7) Quality Engines,
  8-Mutant Anti-Overfitting Saboteur Gate, AAAK Compressor, Steer Harvester, Waste Analyzer
- Pillar 3: 2-Stage Stateless Goldfish -> Isolated Judge Stop Gate v4.3 (C1-C8 contracts, single-stage fallback,
  in-process attached verification, arrow guard, pre-critic summary gate) & PreToolUse Sentinel Dispatcher
"""

import os
import sys
import json
import uuid
import shutil
import tempfile
import unittest
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from autonomy_engine.aaak_compressor import AAAKCompressor
from autonomy_engine.resilient_steer_harvester import harvest_steers_from_steps
from autonomy_engine.session_waste_analyzer import analyze_single_session
from autonomy_engine.anti_overfitting_gate import AntiOverfittingGate
from autonomy_engine.p0_quality_first_engine import run_self_test as run_p0_self_test
from autonomy_engine.p1_quality_first_engine import run_self_test as run_p1_self_test
from knowledge_graph.kg_decay_link_predictor import apply_temporal_decay, ACTR_CLAMP_FLOOR
from knowledge_graph.okf_knowledge_compiler import sync_kb_to_graph
from knowledge_graph.validate_okf import validate_kb_bundle
from hooks.black_hat_analyzer import scan_target
from hooks.agent_stop_black_hat_gate import evaluate as evaluate_stop_gate
from hooks.kg_pre_invocation_hook import extract_recent_inputs, resolve_hybrid_entities


class TestAutonomyKGHooks(unittest.TestCase):
    def test_01_static_black_hat_analyzer_clean_repo(self):
        """Verifies 0 syntax errors and 0 workstation/internal leaks across src/ and agents/."""
        res = scan_target(SRC_DIR)
        self.assertEqual(res["verdict"], "PASS", f"Analyzer failed: {res}")
        self.assertEqual(res["syntax_errors"], [])
        self.assertEqual(res["path_leaks"], [])

    def test_02_aaak_compressor_preserves_thinking_and_thought(self):
        """Verifies both canonical `thinking` and legacy `thought` keys are preserved."""
        step = {
            "type": "PLANNER_RESPONSE",
            "thinking": "\x1b[32mDeep architectural deliberation trace\x1b[0m\n\n\nNext step.",
            "thought": "Legacy thought trace",
            "content": "Checking https://github.com/org/repo/issues/42",
            "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "/workspace/main.py"}}],
        }
        comp = AAAKCompressor.compress_transcript_step(step)
        self.assertIn("Deep architectural deliberation trace", comp["thinking"])
        self.assertNotIn("\x1b[32m", comp["thinking"])
        self.assertEqual(comp["thought"], "Legacy thought trace")
        self.assertIn("gh#org/repo#42", comp["content"])
        self.assertIn("⟪CALL:view_file", comp["packed_action_tuples"])

    def test_03_resilient_steer_harvester(self):
        """Verifies 2-tier preference extraction and operational inquiry exclusion."""
        steps = [
            {"type": "USER_INPUT", "content": "From now on, always use pytest instead of unittest for new suites."},
            {"type": "USER_INPUT", "content": "check if the server is running?"},
        ]
        harvested = harvest_steers_from_steps(steps)
        self.assertEqual(len(harvested), 1)
        self.assertEqual(harvested[0]["tier"], "TIER_1_EXPLICIT")

    def test_04_session_waste_analyzer(self):
        """Verifies detection of redundant idempotent reads (W6) and circular backtracking (W9)."""
        steps = [
            {"type": "PLANNER_RESPONSE", "content": "Reading file", "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "/a.py"}}]},
            {"type": "PLANNER_RESPONSE", "content": "Reading file again", "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "/a.py"}}]},
            {"type": "PLANNER_RESPONSE", "content": "Reading file third time", "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "/a.py"}}]},
        ]
        report = analyze_single_session(steps, conv_id="test-conv")
        self.assertIn("W6", report["detected_patterns"])
        self.assertIn("W9", report["detected_patterns"])

    def test_05_actr_clamping_floor(self):
        """Verifies dormant nodes clamp at A_min = -2.0 rather than decaying to -inf."""
        graph_data = {
            "nodes": [
                {
                    "id": "proj:dormant",
                    "label": "Dormant Project",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "properties": {"confidence": 1.0},
                }
            ],
            "edges": [],
        }
        decayed = apply_temporal_decay(graph_data)
        self.assertEqual(decayed, 1)
        actr = graph_data["nodes"][0]["properties"]["actr_base_activation"]
        self.assertEqual(actr, ACTR_CLAMP_FLOOR)

    def test_06_stop_hook_v43_two_stage_and_single_stage(self):
        """Verifies v4.3 Stop hook: read-only allow, arrow guard allow, unverified block, single-stage allow, and 2-stage Goldfish->Judge allow."""
        temp_dir = tempfile.mkdtemp()
        try:
            # 1. Read-only turn + text arrow '->' in echo -> ALLOW (arrow guard prevents false shell redirection trigger)
            ro_transcript = os.path.join(temp_dir, "ro_transcript.jsonl")
            with open(ro_transcript, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Check status"}) + "\n")
                f.write(json.dumps({
                    "type": "PLANNER_RESPONSE",
                    "content": "Checking",
                    "tool_calls": [{"name": "run_command", "args": {"CommandLine": "echo 'A -> B'"}}],
                }) + "\n")
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "Status is healthy."}) + "\n")

            res_ro = evaluate_stop_gate({
                "conversationId": str(uuid.uuid4()),
                "transcriptPath": ro_transcript,
                "artifactDirectoryPath": temp_dir,
                "agentName": "main",
                "executionNum": 0,
                "terminationReason": "NO_TOOL_CALL",
            })
            self.assertEqual(res_ro["decision"], "allow")

            # 2. Mutating turn without critic -> CONTINUE (block)
            mut_transcript = os.path.join(temp_dir, "mut_transcript.jsonl")
            with open(mut_transcript, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Create app.py"}) + "\n")
                f.write(json.dumps({
                    "type": "PLANNER_RESPONSE",
                    "content": "Writing app.py",
                    "tool_calls": [{"name": "write_to_file", "args": {"TargetFile": "/workspace/app.py"}}],
                }) + "\n")
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "Task is complete."}) + "\n")

            res_mut = evaluate_stop_gate({
                "conversationId": str(uuid.uuid4()),
                "transcriptPath": mut_transcript,
                "artifactDirectoryPath": temp_dir,
                "agentName": "main",
                "executionNum": 0,
                "terminationReason": "NO_TOOL_CALL",
            })
            self.assertEqual(res_mut["decision"], "continue")

            # 3. Mutating turn WITH verified 2-stage Goldfish -> Judge transcripts AND Bottom Summary -> ALLOW
            gf_cid = str(uuid.uuid4())
            jg_cid = str(uuid.uuid4())
            brain_root = os.path.expanduser("~/.gemini/antigravity/brain")
            gf_log_dir = os.path.join(brain_root, gf_cid, ".system_generated", "logs")
            jg_log_dir = os.path.join(brain_root, jg_cid, ".system_generated", "logs")
            os.makedirs(gf_log_dir, exist_ok=True)
            os.makedirs(jg_log_dir, exist_ok=True)
            gf_transcript = os.path.join(gf_log_dir, "transcript.jsonl")
            jg_transcript = os.path.join(jg_log_dir, "transcript.jsonl")

            with open(gf_transcript, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "Probing file...", "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "/workspace/app.py"}}]}) + "\n")
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "Verifying syntax...", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "python3 -m py_compile /workspace/app.py"}}]}) + "\n")
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "## 🐟 FORENSIC_EVIDENCE_DOSSIER\nDISCREPANCY_COUNT: 0"}) + "\n")

            with open(jg_transcript, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "Reading goldfish transcript", "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": gf_transcript}}]}) + "\n")
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "Spot-checking deliverable", "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "/workspace/app.py"}}]}) + "\n")
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "MITM_LAUNDERING: NONE\nCRITIC_VERDICT: APPROVED"}) + "\n")

            verified_transcript = os.path.join(temp_dir, "verified_transcript.jsonl")
            with open(verified_transcript, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Create app.py"}) + "\n")
                f.write(json.dumps({
                    "type": "PLANNER_RESPONSE",
                    "content": "Writing app.py",
                    "tool_calls": [{"name": "write_to_file", "args": {"TargetFile": "/workspace/app.py"}}],
                }) + "\n")
                f.write(json.dumps({
                    "type": "PLANNER_RESPONSE",
                    "content": "Dispatching goldfish",
                    "tool_calls": [{"name": "invoke_subagent", "args": {"Subagents": [{"TypeName": "black-hat-goldfish", "Prompt": "Claim C1: /workspace/app.py exists"}]}}],
                }) + "\n")
                f.write(json.dumps({"type": "TOOL_RESULT", "content": json.dumps({"conversationId": gf_cid})}) + "\n")
                f.write(json.dumps({
                    "type": "PLANNER_RESPONSE",
                    "content": "Dispatching judge",
                    "tool_calls": [{"name": "invoke_subagent", "args": {"Subagents": [{"TypeName": "black-hat-judge", "Prompt": f"Goldfish cid: {gf_cid}"}]}}],
                }) + "\n")
                f.write(json.dumps({"type": "TOOL_RESULT", "content": json.dumps({"conversationId": jg_cid})}) + "\n")
                f.write(json.dumps({
                    "type": "PLANNER_RESPONSE",
                    "content": "### 📋 Summary of Approved Response & Deliverables\n* Created `/workspace/app.py`.\n\n`CRITIC_VERDICT: APPROVED | GCS = 1.000 | 8/8 Checks Passed`",
                }) + "\n")

            res_ver = evaluate_stop_gate({
                "conversationId": str(uuid.uuid4()),
                "transcriptPath": verified_transcript,
                "artifactDirectoryPath": temp_dir,
                "agentName": "main",
                "executionNum": 0,
                "terminationReason": "NO_TOOL_CALL",
            })
            shutil.rmtree(os.path.join(brain_root, gf_cid), ignore_errors=True)
            shutil.rmtree(os.path.join(brain_root, jg_cid), ignore_errors=True)
            self.assertEqual(res_ver["decision"], "allow", f"Expected allow, got: {res_ver}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_07_pre_invocation_context_summary_strip_and_okf_cobundle(self):
        """Verifies <CONTEXT_SUMMARY> stripping and OKF v0.2 + 1-hop matching in kg_pre_invocation_hook.py."""
        tf = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        tf.write(json.dumps({
            "type": "USER_INPUT",
            "content": "<CONTEXT_SUMMARY>Old topic about LegacyProject</CONTEXT_SUMMARY>\nTell me about antigravity-hub architecture"
        }) + "\n")
        tf.close()
        try:
            inputs = extract_recent_inputs(tf.name)
            self.assertEqual(len(inputs), 1)
            self.assertNotIn("LegacyProject", inputs[0])

            kg_data = {
                "nodes": [
                    {"id": "infra:antigravity-hub", "label": "Antigravity Web Hub", "type": "Infrastructure", "aliases": ["antigravity-hub"], "description": "Multi-model router", "properties": {}},
                    {"id": "infra:ccpa-sidecar", "label": "CCPA Vertex Sidecar", "type": "Component", "description": "Protocol proxy", "properties": {}},
                    {"id": "okf:antigravity-web-hub-architecture", "label": "Antigravity Web Hub Architecture", "type": "OKF_Architecture", "aliases": ["antigravity-hub"], "description": "OKF dossier", "properties": {"kb_path": "kb/architecture/antigravity_hub.md", "tags": ["antigravity", "architecture"]}},
                ],
                "edges": [
                    {"source": "infra:antigravity-hub", "target": "infra:ccpa-sidecar", "relation": "ROUTES_TO"},
                ],
            }
            matched = resolve_hybrid_entities(inputs[0], kg_data)
            matched_ids = [m["id"] for m in matched]
            self.assertIn("infra:antigravity-hub", matched_ids)
            self.assertIn("infra:ccpa-sidecar", matched_ids)
            self.assertIn("okf:antigravity-web-hub-architecture", matched_ids)
        finally:
            os.remove(tf.name)

    def test_08_okf_v02_bundle_validation_and_compiler(self):
        """Verifies public Open Knowledge Format (OKF v0.2) bundle validation and KG compilation."""
        kb_root = os.path.join(REPO_ROOT, "kb")
        val_res = validate_kb_bundle(kb_root)
        self.assertTrue(val_res["valid"], f"OKF validation failed: {val_res}")
        self.assertGreaterEqual(val_res["files_checked"], 4)

        temp_graph = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        try:
            sync_res = sync_kb_to_graph(kb_root=kb_root, graph_path=temp_graph)
            self.assertEqual(sync_res["status"], "ok")
            self.assertGreaterEqual(sync_res["synced_dossiers"], 2)
        finally:
            if os.path.exists(temp_graph):
                os.remove(temp_graph)

    def test_09_p0_p1_quality_engines_and_saboteur_benchmark(self):
        """Verifies P0 (CB-1..CB-7), P1 (P1-CB-1..P1-CB-7), and 8-Mutant Saboteur self-tests."""
        p0_res = run_p0_self_test()
        self.assertEqual(p0_res["verdict"], "PASS", f"P0 failed: {p0_res}")

        p1_res = run_p1_self_test()
        self.assertEqual(p1_res["verdict"], "PASS", f"P1 failed: {p1_res}")

        sab_res = AntiOverfittingGate().run_saboteur_benchmark()
        self.assertEqual(sab_res["verdict"], "PASS", f"Saboteur failed: {sab_res}")
        self.assertEqual(sab_res["saboteur_recall_pct"], 100.0)

    def test_10_sentinel_pre_tool_use_dispatcher(self):
        """Verifies PreToolUse sentinel_dispatch.py blocks destructive commands and allows safe commands."""
        dispatcher = os.path.join(SRC_DIR, "hooks", "sentinel_dispatch.py")
        bad_payload = json.dumps({"toolName": "run_command", "toolArgs": {"CommandLine": "rm -rf /"}})
        p_bad = subprocess.run([sys.executable, dispatcher], input=bad_payload, text=True, capture_output=True)
        self.assertIn('"decision": "ask"', p_bad.stdout)

        good_payload = json.dumps({"toolName": "run_command", "toolArgs": {"CommandLine": "echo hello"}})
        p_good = subprocess.run([sys.executable, dispatcher], input=good_payload, text=True, capture_output=True)
        self.assertIn('"decision": "allow"', p_good.stdout)


if __name__ == "__main__":
    unittest.main()
