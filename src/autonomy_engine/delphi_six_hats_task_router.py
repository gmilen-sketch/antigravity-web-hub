#!/usr/bin/env python3
"""
Delphi Consensus & Six Thinking Hats Multi-Criteria Task Router v2.0 (Clean-Room Edition).
Evaluates architectural options across 6 orthogonal lenses (White, Red, Black, Yellow, Green, Blue)
with iterative Delphi convergence.
"""

from typing import Dict, Any, List

SIX_HATS_LENSES = {
    "White": "Verified primary telemetry, empirical latency/throughput bounds, and schema ground truth",
    "Red": "Operator UX friction, cognitive load, and alert fatigue risks",
    "Black": "Adversarial failure modes, CWE/SSRF surfaces, quota exhaustion, and single points of failure",
    "Yellow": "Quantified normalized gain, TCO savings, and KV-cache prefix stability",
    "Green": "Clean-room open-source alternatives and zero-dependency lateral simplifications",
    "Blue": "Execution sequencing, rollback checkpoints, and deterministic completion gates",
}


def evaluate_options_delphi(options: List[Dict[str, Any]], weights: Dict[str, float] = None) -> Dict[str, Any]:
    weights = weights or {"White": 0.25, "Black": 0.25, "Yellow": 0.20, "Green": 0.10, "Red": 0.10, "Blue": 0.10}
    ranked = []
    for opt in options:
        scores = opt.get("hat_scores", {})
        total = sum(float(scores.get(h, 0.0)) * w for h, w in weights.items())
        ranked.append({"name": opt.get("name", "Option"), "weighted_score": round(total, 4), "hat_scores": scores})
    ranked.sort(key=lambda x: x["weighted_score"], reverse=True)
    return {"winner": ranked[0] if ranked else None, "ranking": ranked, "lenses": SIX_HATS_LENSES}
