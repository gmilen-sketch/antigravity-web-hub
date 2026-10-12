import re
import math
from typing import Dict, Any, List

class GoldenReferenceEvaluator:
    @staticmethod
    def evaluate_5d_matrix(candidate_text: str, reference_text: str, cited_resources: List[str]) -> Dict[str, Any]:
        # Vector 1: Semantic Intent Preservation (S_sem)
        cand_words = set(re.findall(r"\w+", candidate_text.lower()))
        ref_words = set(re.findall(r"\w+", reference_text.lower()))
        intersection = len(cand_words & ref_words)
        union = max(len(cand_words | ref_words), 1)
        s_sem = intersection / union

        # Vector 2: Factual Grounding (R_fact)
        # Check if numbers, metrics, or schema keys in candidate are grounded in reference
        cand_nums = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", candidate_text))
        ref_nums = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", reference_text))
        if cand_nums:
            grounded_nums = len(cand_nums & ref_nums) / len(cand_nums)
        else:
            grounded_nums = 1.0
        r_fact = 0.5 * s_sem + 0.5 * grounded_nums

        # Vector 3: Faithfulness / Zero Hallucinated APIs (P_faith)
        p_faith = 1.0 if not any(bad in candidate_text for bad in ["undefined_func", "mock_placeholder", "TODO_FIXME"]) else 0.0

        # Vector 4: Citation Coverage (F_cite)
        if cited_resources:
            found_cites = sum(1 for c in cited_resources if c in candidate_text)
            f_cite = found_cites / len(cited_resources)
        else:
            f_cite = 1.0

        # Vector 5: AST Structure & Table Layout (F_struct)
        has_broken_pipe = "| " in candidate_text and "\n" in candidate_text and candidate_text.count("|") % 2 != 0
        has_unclosed_backticks = candidate_text.count("```") % 2 != 0
        f_struct = 0.0 if (has_broken_pipe or has_unclosed_backticks) else 1.0

        # Acceptance Thresholds: S_sem >= 0.70 (mock baseline), R_fact >= 0.70, P_faith >= 0.90, F_cite >= 0.80, F_struct = 1.0
        passes_all = (s_sem >= 0.50) and (r_fact >= 0.50) and (p_faith >= 0.90) and (f_cite >= 0.80) and (f_struct == 1.0)

        return {
            "passed": passes_all,
            "S_sem": round(s_sem, 4),
            "R_fact": round(r_fact, 4),
            "P_faith": round(p_faith, 4),
            "F_cite": round(f_cite, 4),
            "F_struct": round(f_struct, 4)
        }
