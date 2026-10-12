#!/usr/bin/env python3
"""
Deterministic AI Writing Trope & Contrastive-Binary Scanner v2.0 (Clean-Room Edition).
Scans prose for banned AI filler tropes ('delve into', 'testament to', 'tapestry of')
and contrastive binaries ('not X, but Y' / 'not because of X, but rather Y').
"""

import re
from typing import Dict, Any, List

BANNED_TROPES = [
    (r"(?i)\bnot\s+only\b[^.?!]{1,60}\bbut\s+(also|rather)\b", "CONTRASTIVE_BINARY"),
    (r"(?i)\bnot\s+because\s+of\b[^.?!]{1,60}\bbut\s+rather\b", "CONTRASTIVE_BINARY"),
    (r"(?i)\b(delve\s+into|tapestry\s+of|testament\s+to|beacon\s+of|symphony\s+of)\b", "AI_CLICHE_TROPE"),
    (r"(?i)\b(it\s+is\s+important\s+to\s+note\s+that|in\s+today's\s+fast-paced)\b", "CONVERSATIONAL_FLUFF"),
]


def scan_prose_tropes(text: str) -> Dict[str, Any]:
    violations: List[Dict[str, str]] = []
    for pat, label in BANNED_TROPES:
        for m in re.finditer(pat, text or ""):
            violations.append({"type": label, "match": m.group(0)})
    return {"clean": len(violations) == 0, "violation_count": len(violations), "violations": violations}
