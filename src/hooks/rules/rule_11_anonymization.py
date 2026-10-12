#!/usr/bin/env python3
"""Rule 11: Clean-Room Path & Secret Anonymization Gate."""
import re
from typing import Dict, Any, Optional

HOME_PREFIX = "/usr/local/" + "google/home/"

def check(tool_name: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if tool_name in ("write_to_file", "replace_file_content"):
        target = str(tool_args.get("TargetFile", ""))
        content = str(tool_args.get("CodeContent", "")) + str(tool_args.get("ReplacementContent", ""))
        if "/public/" in target or "README.md" in target:
            if re.search(re.escape(HOME_PREFIX) + r"[A-Za-z0-9_.-]+", content):
                return {
                    "decision": "block",
                    "reason": "Rule 11 Violation: Hardcoded local workstation path detected in shared/public artifact.",
                }
    return None
