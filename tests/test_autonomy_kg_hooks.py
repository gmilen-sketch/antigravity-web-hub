#!/usr/bin/env python3
"""
Comprehensive Unit & Integration Test Suite for Antigravity Web Hub Autonomy Upgrades:
- Pillar 1: Knowledge Graph, ACT-R Clamping Floor (A_min = -2.0), Unified Warm Cache, PreInvocation Hook
- Pillar 2: Nightly Dreaming v4.0, AAAK Compressor (CoT retention), Resilient Steer Harvester, Session Waste Analyzer
- Pillar 3: Black-Hat Stop Gate v3.0 (Dual Behavioral Contract & Structural Proof) & Black-Hat Static Analyzer
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
from autonomy_engine.resilient_steer_harvester import ResilientPreferenceSieve, harvest_steers_from_steps
from autonomy_engine.session_waste_analyzer import analyze_single_session
from knowledge_graph.kg_decay_link_predictor import apply_temporal_decay, ACTR_CLAMP_FLOOR
from hooks.black_hat_analyzer import scan_target
from hooks.agent_stop_black_hat_gate import evaluate as evaluate_stop_gate


class TestAutonomyKGHooks(unittest.TestCase):
    def test_01_static_black_hat_analyzer_clean_repo(self):
        """Verifies 0 syntax errors and 0 workstation/internal leaks across src/ and agents/."""
        res = scan_target(SRC_DIR)
        self.assertEqual(res["verdict"], "PASS", f"Analyzer failed: {res}")
        self.assertEqual(res["syntax_errors"], [])
        self.assertEqual(res["path_leaks"], [])

    def test_02_aaak_compressor_preserves_thinking_and_thought(self):
        """Verifies Bug #1 fix: both canonical `thinking` and legacy `thought` keys are preserved."""
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

    def test_06_stop_hook_dual_contract_and_structural_proof(self):
        """Verifies Stop hook allows read-only turns, blocks unverified mutations, and allows verified critic."""
        temp_dir = tempfile.mkdtemp()
        try:
            # 1. Read-only turn -> ALLOW
            ro_transcript = os.path.join(temp_dir, "ro_transcript.jsonl")
            with open(ro_transcript, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "What is 2+2?"}) + "\n")
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "2+2 is 4."}) + "\n")

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

            # 3. Mutating turn WITH verified black-hat-critic transcript -> ALLOW
            critic_cid = str(uuid.uuid4())
            brain_root = os.path.expanduser("~/.gemini/antigravity/brain")
            critic_log_dir = os.path.join(brain_root, critic_cid, ".system_generated", "logs")
            os.makedirs(critic_log_dir, exist_ok=True)
            critic_transcript = os.path.join(critic_log_dir, "transcript.jsonl")
            with open(critic_transcript, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "Auditing...", "tool_calls": [{"name": "view_file", "args": {}}]}) + "\n")
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "Checking...", "tool_calls": [{"name": "list_dir", "args": {}}]}) + "\n")
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "All checks passed.\nCRITIC_VERDICT: APPROVED"}) + "\n")

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
                    "content": "Dispatching critic",
                    "tool_calls": [{"name": "invoke_subagent", "args": {"Subagents": [{"TypeName": "black-hat-critic"}]}}],
                }) + "\n")
                f.write(json.dumps({
                    "type": "TOOL_RESULT",
                    "content": json.dumps({"conversationId": critic_cid}),
                }) + "\n")
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "Task is complete."}) + "\n")

            res_ver = evaluate_stop_gate({
                "conversationId": str(uuid.uuid4()),
                "transcriptPath": verified_transcript,
                "artifactDirectoryPath": temp_dir,
                "agentName": "main",
                "executionNum": 0,
                "terminationReason": "NO_TOOL_CALL",
            })
            shutil.rmtree(os.path.join(brain_root, critic_cid), ignore_errors=True)
            self.assertEqual(res_ver["decision"], "allow", f"Expected allow, got: {res_ver}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
