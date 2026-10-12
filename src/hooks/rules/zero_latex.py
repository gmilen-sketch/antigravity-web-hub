#!/usr/bin/env python3
"""
Zero-Raw-LaTeX Document Export Gate (Clean-Room Edition).
Prevents raw LaTeX math tokens ($$, \frac, \text{}) from leaking into Google Docs / Slides REST imports.
"""
import re
from typing import Dict, Any, Optional

RAW_LATEX_PATTERNS = [
    r"\$\$[^$]+\$\$",
    r"\\frac\s*\{",
    r"\\text\s*\{",
    r"\\times\b",
    r"\\geq\b",
    r"\\leq\b",
]


def check(tool_name: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if tool_name in ("mcp_google_workspace_create_doc", "mcp_google_workspace_append_doc"):
        body = str(tool_args.get("content", "")) + str(tool_args.get("text", ""))
        for pat in RAW_LATEX_PATTERNS:
            if re.search(pat, body):
                return {
                    "decision": "block",
                    "reason": "Zero-LaTeX Gate: Use clean Unicode math symbols (×, ÷, ≥, ≤, →, —) instead of raw LaTeX tokens in Google Docs exports.",
                }
    return None
