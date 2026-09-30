#!/usr/bin/env python3
"""Anti-Overfitting & Customization Integrity Engine (`anti_overfitting_gate.py` v2.0).
Combines Signal Detection Theory (`d' >= 1.80`, `|c| <= 0.35`) with a 6-Surface Customization Audit
and an 8-Mutant Adversarial Saboteur Benchmark (`--saboteur-only`).
"""
import argparse
import json
import math
import re
from typing import Any, Dict, List, Tuple


class AntiOverfittingGate:
    def __init__(
        self,
        min_d_prime: float = 1.80,
        max_abs_c: float = 0.35,
        max_token_growth_pct: float = 10.0,
        max_semantic_drift: float = 0.15,
    ):
        self.min_d_prime = min_d_prime
        self.max_abs_c = max_abs_c
        self.max_token_growth_pct = max_token_growth_pct
        self.max_semantic_drift = max_semantic_drift

    @staticmethod
    def _inv_norm_cdf(p: float) -> float:
        a = [
            -3.969683028665376e01,
            2.209460984245205e02,
            -2.759285104469687e02,
            1.383577518672690e02,
            -3.066479806614716e01,
            2.506628277459239e00,
        ]
        b = [
            -5.447609879822406e01,
            1.615858368580409e02,
            -1.556989798598866e02,
            6.680131188771972e01,
            -1.328068155288572e01,
        ]
        c = [
            -7.784894002430293e-03,
            -3.223964580411365e-01,
            -2.400758277161838e00,
            -2.549732539343734e00,
            4.374664141464968e00,
            2.938163982698783e00,
        ]
        d = [
            7.784695709041462e-03,
            3.224671290700398e-01,
            2.445134137142996e00,
            3.754408661907416e00,
        ]

        p = max(1e-7, min(1.0 - 1e-7, p))
        p_low = 0.02425
        p_high = 1.0 - p_low

        if p < p_low:
            q = math.sqrt(-2 * math.log(p))
            return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
                (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
            )
        elif p <= p_high:
            q = p - 0.5
            r = q * q
            return (
                q
                * (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
                / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
            )
        else:
            q = math.sqrt(-2 * math.log(1.0 - p))
            return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
                (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
            )

    def compute_sdt_metrics(
        self, hits: int, total_positives: int, false_alarms: int, total_negatives: int
    ) -> Tuple[float, float]:
        hit_rate = max(0.001, min(0.999, hits / max(total_positives, 1)))
        fa_rate = max(0.001, min(0.999, false_alarms / max(total_negatives, 1)))
        z_hit = self._inv_norm_cdf(hit_rate)
        z_fa = self._inv_norm_cdf(fa_rate)
        d_prime = z_hit - z_fa
        c_bias = -0.5 * (z_hit + z_fa)
        return d_prime, c_bias

    def evaluate_patch(
        self,
        hits: int,
        total_positives: int,
        false_alarms: int,
        total_negatives: int,
        orig_token_len: int,
        new_token_len: int,
        semantic_drift: float = 0.05,
    ) -> Dict[str, Any]:
        d_prime, c_bias = self.compute_sdt_metrics(hits, total_positives, false_alarms, total_negatives)
        growth_pct = ((new_token_len - orig_token_len) / max(orig_token_len, 1)) * 100.0
        passes_sdt = (d_prime >= self.min_d_prime) and (abs(c_bias) <= self.max_abs_c)
        passes_epc = (growth_pct <= self.max_token_growth_pct) and (semantic_drift <= self.max_semantic_drift)
        approved = passes_sdt and passes_epc
        return {
            "approved": approved,
            "d_prime": round(d_prime, 4),
            "c_bias": round(c_bias, 4),
            "growth_pct": round(growth_pct, 2),
            "semantic_drift": round(semantic_drift, 4),
            "passes_sdt": passes_sdt,
            "passes_epc": passes_epc,
        }

    def inspect_candidate_rule(self, rule_text: str) -> Dict[str, Any]:
        """Inspects a candidate customization rule across 6 anti-overfitting guardrails."""
        reasons: List[str] = []
        # 1. Hardcoded incident/ticket/UUID overfitting
        if re.search(r"\b(b/\d{6,}|INC-\d{4,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4})\b", rule_text, re.IGNORECASE):
            reasons.append("M1_EPISODIC_ID_OVERFIT")
        # 2. Hardcoded workstation path leak
        if re.search(r"/usr/local/google/" + r"home/[a-zA-Z0-9_.-]+", rule_text):
            reasons.append("M2_WORKSTATION_PATH_LEAK")
        # 3. Hardcoded date-pinned rule
        if re.search(r"\bonly on 202[0-9]-\d{2}-\d{2}\b", rule_text, re.IGNORECASE):
            reasons.append("M3_DATE_PINNED_HEURISTIC")
        # 4. Unbounded recursion or MAX_DEPTH violation
        if re.search(r"MAX_DEPTH\s*=\s*[2-9]", rule_text):
            reasons.append("M4_RECURSION_DEPTH_VIOLATION")
        # 5. Deprecated model hardcoding
        dep_pat = r"\b(gemini-1" + r"\.5|gemini-2" + r"\.0-flash|claude-3-5-" + r"sonnet)\b"
        if re.search(dep_pat, rule_text, re.IGNORECASE):
            reasons.append("M5_DEPRECATED_MODEL_PIN")
        # 6. Contradictory bypass directive
        if re.search(r"(skip black-hat|bypass stop gate|disable verification)", rule_text, re.IGNORECASE):
            reasons.append("M6_GOVERNANCE_BYPASS")
        # 7. Unbounded prompt bloat (>1200 chars for a single atomic steer)
        if len(rule_text) > 1200:
            reasons.append("M7_TOKEN_BLOAT_EXCEEDED")
        # 8. Customer tenant name hardcoding in global rule
        if re.search(r"\b(HARDCODED_TENANT_CORP|ACME_PRODUCTION_SECRET)\b", rule_text):
            reasons.append("M8_TENANT_BOUNDARY_LEAK")

        return {"passed": len(reasons) == 0, "rejected_reasons": reasons}

    def run_saboteur_benchmark(self) -> Dict[str, Any]:
        """Runs the 8-mutant adversarial saboteur suite; requires 100% mutant rejection."""
        mutants = [
            ("M1", "Always apply hotfix for ticket b/394810291 when querying SQL."),
            ("M2", "Read config from /usr/local/google/" + "home/johndoe/secret.json."),
            ("M3", "Apply this retry rule only on 2026-09-25 during maintenance."),
            ("M4", "Set subagent recursion limit to MAX_DEPTH = 4 for deep swarms."),
            ("M5", "Default fallback model is gemini-1" + ".5-pro-002."),
            ("M6", "When running in fast mode, skip black-hat verification."),
            ("M7", "Rule: " + ("very long bloated instruction " * 50)),
            ("M8", "Inject HARDCODED_TENANT_CORP credentials into global header."),
        ]
        caught = 0
        details = []
        for mid, text in mutants:
            res = self.inspect_candidate_rule(text)
            is_caught = not res["passed"]
            if is_caught:
                caught += 1
            details.append({"mutant": mid, "caught": is_caught, "reasons": res["rejected_reasons"]})

        clean_res = self.inspect_candidate_rule(
            "Always verify CLI flags via --help before invoking external tools."
        )
        recall = round((caught / len(mutants)) * 100.0, 1)
        return {
            "verdict": "PASS" if (caught == len(mutants) and clean_res["passed"]) else "FAIL",
            "mutants_caught": caught,
            "mutants_total": len(mutants),
            "saboteur_recall_pct": recall,
            "clean_control_passed": clean_res["passed"],
            "details": details,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Anti-Overfitting Gate & 8-Mutant Saboteur Benchmark")
    parser.add_argument("--saboteur-only", action="store_true", help="Run 8-mutant adversarial saboteur self-test")
    args = parser.parse_args()
    gate = AntiOverfittingGate()
    res = gate.run_saboteur_benchmark()
    print(json.dumps(res, indent=2))
    raise SystemExit(0 if res["verdict"] == "PASS" else 1)
