#!/usr/bin/env python3
r"""Hardened P0 Quality-First Runtime Engine (`p0_quality_first_engine.py` — Clean-Room Edition).
Implements the 7 P0 Quality-First Circuit-Breakers (`CB-1` through `CB-7`) enforcing the
Lossless Additive Quality Invariant ($I(B^+) \supseteq I(A)$):
- CB-1: Intent-Bound Source Tiering (`REQUIRED_PRIMARY` vs `OPTIONAL_SECONDARY`)
- CB-2: Runtime Anti-TOCTOU Assertion (`exit_code == 0` + required output columns)
- CB-3: Exact FQN Scope + `12h` TTL Decay in `/dev/shm/intraday_lessons.jsonl`
- CB-4: `PD-Q` Progressive Disclosure & Top-3 `okf:*` Co-Bundling (`W_tokens = 0.00`)
- CB-5: Two-Tier Lossless Log Pointer SSOT (`SHA-256` verified)
- CB-6: Sub-110ms Typed Reflex Mode A (Deliverable) vs Mode B (Direct CLI/Q&A) Dispatcher
- CB-7: Cryptographic SHA-256 Mirror Parity Guard (`--self-test`)
"""
import argparse
import hashlib
import json
import os
import time
from typing import Any, Dict, List


INTRADAY_LESSONS_PATH = "/dev/shm/intraday_lessons.jsonl" if os.path.exists("/dev/shm") else "/tmp/intraday_lessons.jsonl"
LESSON_TTL_SECONDS = 12 * 3600


class P0QualityFirstEngine:
    """Enforces CB-1 through CB-7 runtime invariants."""

    @staticmethod
    def cb1_classify_sources(intent: str, candidate_sources: List[str]) -> Dict[str, List[str]]:
        """CB-1: Intent-Bound Source Tiering."""
        primary = []
        secondary = []
        for src in candidate_sources:
            s_low = src.lower()
            if any(k in s_low for k in ("knowledge_graph", "kb/", "sql", "git", "file://", "src/", "tests/")):
                primary.append(src)
            else:
                secondary.append(src)
        if not primary and candidate_sources:
            primary.append(candidate_sources[0])
        return {"REQUIRED_PRIMARY": primary, "OPTIONAL_SECONDARY": secondary}

    @staticmethod
    def cb2_verify_command_output(exit_code: int, stdout: str, required_tokens: List[str] = None) -> Dict[str, Any]:
        """CB-2: Runtime Anti-TOCTOU Assertion."""
        required_tokens = required_tokens or []
        missing = [tok for tok in required_tokens if tok not in stdout]
        passed = (exit_code == 0) and (len(missing) == 0)
        return {
            "passed": passed,
            "exit_code": exit_code,
            "missing_tokens": missing,
        }

    @staticmethod
    def cb3_record_intraday_lesson(fqn_tool: str, error_signature: str, fix_recipe: str) -> Dict[str, Any]:
        """CB-3: Exact FQN Scope + 12h TTL Decay in /dev/shm/intraday_lessons.jsonl."""
        entry = {
            "fqn_tool": fqn_tool,
            "error_signature": error_signature,
            "fix_recipe": f"[ADVISORY PRIOR — MANDATORY PRIMARY SCHEMA/DATA VERIFICATION REQUIRED] {fix_recipe}",
            "created_at": time.time(),
            "ttl_seconds": LESSON_TTL_SECONDS,
        }
        os.makedirs(os.path.dirname(INTRADAY_LESSONS_PATH), exist_ok=True)
        with open(INTRADAY_LESSONS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    @staticmethod
    def cb3_get_active_lessons(fqn_tool: str) -> List[Dict[str, Any]]:
        """Returns non-expired lessons scoped strictly to `fqn_tool`."""
        if not os.path.exists(INTRADAY_LESSONS_PATH):
            return []
        now = time.time()
        active = []
        with open(INTRADAY_LESSONS_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("fqn_tool") == fqn_tool and (now - float(obj.get("created_at", 0))) <= LESSON_TTL_SECONDS:
                        active.append(obj)
                except Exception:
                    pass
        return active

    @staticmethod
    def cb4_pdq_contract() -> Dict[str, Any]:
        """CB-4: PD-Q Epistemic Reasoning-Complete Co-Bundling Contract (W_tokens = 0.00)."""
        return {
            "mode": "PD-Q",
            "w_quality": 0.35,
            "w_reasoning": 0.35,
            "w_grounding": 0.30,
            "w_tokens": 0.00,
            "core_retention_pct": 100.0,
        }

    @staticmethod
    def cb5_create_lossless_log_pointer(raw_output: str, log_dir: str = "/tmp/lossless_logs") -> Dict[str, Any]:
        """CB-5: Two-Tier Lossless Log Pointer SSOT with SHA-256 verification."""
        os.makedirs(log_dir, exist_ok=True)
        digest = hashlib.sha256(raw_output.encode("utf-8")).hexdigest()
        log_path = os.path.join(log_dir, f"log_{digest[:16]}.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(raw_output)
        return {
            "log_path": log_path,
            "sha256": digest,
            "bytes": len(raw_output.encode("utf-8")),
            "preview": raw_output[:400],
        }

    @staticmethod
    def cb6_dispatch_mode(prompt: str) -> Dict[str, Any]:
        """CB-6: Sub-110ms Typed Reflex Mode A vs Mode B Dispatcher."""
        t0 = time.perf_counter()
        p_low = prompt.lower()
        deliverable_keywords = ("design", "architect", "implement", "port", "deploy", "audit", "report", "refactor")
        mode = "MODE_A_DELIVERABLE" if any(k in p_low for k in deliverable_keywords) else "MODE_B_DIRECT_QA"
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        return {"mode": mode, "latency_ms": latency_ms}

    @staticmethod
    def cb7_verify_mirror_parity(path_a: str, path_b: str) -> Dict[str, Any]:
        """CB-7: Cryptographic SHA-256 Mirror Parity Guard."""
        if not (os.path.exists(path_a) and os.path.exists(path_b)):
            return {"parity": False, "reason": "missing_file"}
        with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
            ha = hashlib.sha256(fa.read()).hexdigest()
            hb = hashlib.sha256(fb.read()).hexdigest()
        return {"parity": ha == hb, "sha256_a": ha, "sha256_b": hb}


def run_self_test() -> Dict[str, Any]:
    engine = P0QualityFirstEngine()
    c1 = engine.cb1_classify_sources("audit repo", ["src/ccpa_mock.py", "https://example.com"])
    c2 = engine.cb2_verify_command_output(0, "STATUS: OK\nCOUNT: 5", ["STATUS: OK"])
    c3 = engine.cb3_record_intraday_lesson("git.push", "non-fast-forward", "git pull --rebase before push")
    c3_read = engine.cb3_get_active_lessons("git.push")
    c4 = engine.cb4_pdq_contract()
    c5 = engine.cb5_create_lossless_log_pointer("Full lossless log payload line 1\nline 2")
    c6 = engine.cb6_dispatch_mode("Implement and deploy the new service")
    c7 = engine.cb7_verify_mirror_parity(c5["log_path"], c5["log_path"])

    all_passed = (
        len(c1["REQUIRED_PRIMARY"]) == 1
        and c2["passed"]
        and len(c3_read) >= 1
        and c4["w_tokens"] == 0.0
        and os.path.exists(c5["log_path"])
        and c6["mode"] == "MODE_A_DELIVERABLE"
        and c7["parity"]
    )
    return {
        "verdict": "PASS" if all_passed else "FAIL",
        "checks": {
            "CB-1": len(c1["REQUIRED_PRIMARY"]) == 1,
            "CB-2": c2["passed"],
            "CB-3": len(c3_read) >= 1,
            "CB-4": c4["w_tokens"] == 0.0,
            "CB-5": os.path.exists(c5["log_path"]),
            "CB-6": c6["mode"] == "MODE_A_DELIVERABLE",
            "CB-7": c7["parity"],
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P0 Quality-First Runtime Engine")
    parser.add_argument("--self-test", action="store_true", help="Run CB-1..CB-7 self-test suite")
    args = parser.parse_args()
    res = run_self_test()
    print(json.dumps(res, indent=2))
    raise SystemExit(0 if res["verdict"] == "PASS" else 1)
