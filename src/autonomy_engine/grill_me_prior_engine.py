#!/usr/bin/env python3
"""
Skill-Triggered Bayesian Self-Grill Prior Engine v2.5 (Clean-Room Customer Edition).
Classifies incoming tasks into 4 complexity tiers (C0_BYPASS, C1_INTERACTIVE_GRILL,
C2_GUARDRAILS_ONLY, C3_FULL_SELF_GRILL) and maintains Beta-Binomial & Debiased
Hunter MM Bradley-Terry priors across clean-room deliverable modalities:
- markdown_docs, tabular_sheets, presentation_slides, web_ui, architecture_diagram, code_diff
"""

import re
import math
from typing import Dict, Any, List

DEFAULT_MODALITY_PRIORS: Dict[str, Dict[str, Any]] = {
    "web_ui": {
        "alpha": 18.0,
        "beta": 2.0,
        "elo": 1618.0,
        "invariants": [
            "svg_text_outside_box == 0 (padLeft/padRight >= 4.0px on pills, >= 6.0px on cards)",
            "svg_line_cuts_card == 0 and svg_line_cuts_text == 0",
            "svg_sibling_box_overlap == 0 and html_box_overflow == 0",
            "fitAllSvgTextToBoxes(root) runtime clamping enabled",
        ],
    },
    "markdown_docs": {
        "alpha": 16.0,
        "beta": 2.0,
        "elo": 1585.0,
        "invariants": [
            "3-Tab Inverted-Pyramid (Arm E): Tab 1 Human BLUF <= 400 words, Tab 2 Full Report, Tab 3 AGENT-SSOT-v1",
            "Centered 516.0 pt tables and diagrams; zero raw LaTeX tokens",
        ],
    },
    "presentation_slides": {
        "alpha": 15.0,
        "beta": 2.0,
        "elo": 1572.0,
        "invariants": [
            "720 x 405 pt #FFFFFF canvas with 4 non-overlapping cards (W = 151.51 pt)",
            "3-shape elementGroup 2-bar +-45 deg vector chevron connectors (W = 16.51 pt)",
        ],
    },
    "tabular_sheets": {
        "alpha": 15.0,
        "beta": 2.0,
        "elo": 1568.0,
        "invariants": [
            "1-Sheet 3-Row Staging Diff (Row 2: Current, Row 3: Planned, Row 4: Delta) before mutation",
        ],
    },
    "architecture_diagram": {
        "alpha": 16.0,
        "beta": 2.0,
        "elo": 1590.0,
        "invariants": [
            "Orthogonal Manhattan routing with r = 5.5px rounded corners and zero card intersections",
            "2x2 grid aspect ratio <= 2.2:1 with BENTO 6-tier semantic zone tints",
        ],
    },
    "code_diff": {
        "alpha": 17.0,
        "beta": 2.0,
        "elo": 1602.0,
        "invariants": [
            "Zero bare except:pass silent fallbacks and 100% unit test pass rate",
        ],
    },
}


def classify_task_tier(prompt: str) -> Dict[str, Any]:
    p = (prompt or "").strip().lower()
    words = p.split()
    if len(words) <= 6 and not re.search(r"\b(build|architect|deploy|design|dashboard|ui|slide|doc|migrate)\b", p):
        return {"tier": "C0_BYPASS", "modalities": []}

    modalities: List[str] = []
    if re.search(r"\b(ui|html|svg|dashboard|portal|web|widget|css)\b", p):
        modalities.append("web_ui")
    if re.search(r"\b(doc|report|document|markdown|ssot)\b", p):
        modalities.append("markdown_docs")
    if re.search(r"\b(slide|deck|presentation|keynote)\b", p):
        modalities.append("presentation_slides")
    if re.search(r"\b(sheet|spreadsheet|ledger|table|csv)\b", p):
        modalities.append("tabular_sheets")
    if re.search(r"\b(diagram|topology|mermaid|bento|architecture)\b", p):
        modalities.append("architecture_diagram")
    if re.search(r"\b(code|script|refactor|implement|test|fix|build)\b", p):
        modalities.append("code_diff")

    if not modalities:
        return {"tier": "C2_GUARDRAILS_ONLY", "modalities": ["code_diff"]}

    tier = "C3_FULL_SELF_GRILL" if len(modalities) >= 2 or "web_ui" in modalities else "C2_GUARDRAILS_ONLY"
    locked = {m: DEFAULT_MODALITY_PRIORS[m] for m in modalities if m in DEFAULT_MODALITY_PRIORS}
    return {"tier": tier, "modalities": modalities, "locked_priors": locked}


def update_beta_binomial_prior(alpha: float, beta: float, passed: bool, decay: float = 0.98) -> Dict[str, float]:
    new_a = (alpha * decay) + (1.0 if passed else 0.0)
    new_b = (beta * decay) + (0.0 if passed else 1.0)
    mean = new_a / (new_a + new_b)
    return {"alpha": round(new_a, 4), "beta": round(new_b, 4), "posterior_mean": round(mean, 4)}
