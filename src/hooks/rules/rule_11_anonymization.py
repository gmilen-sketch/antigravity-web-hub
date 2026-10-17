#!/usr/bin/env python3
"""Rule 11: Clean-Room Path & Secret Anonymization Gate."""
import os
import re
from typing import Dict, Any, Optional


def check(tool_name: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if tool_name in ("write_to_file", "replace_file_content", "write_file", "edit_file"):
        target = str(tool_args.get("TargetFile", tool_args.get("Path", "")))
        content = (
            str(tool_args.get("CodeContent", ""))
            + str(tool_args.get("ReplacementContent", ""))
            + str(tool_args.get("Content", ""))
            + str(tool_args.get("Replacement", ""))
        )
        home_dir = os.path.expanduser("~")
        if "/public/" in target or "README.md" in target:
            if home_dir and len(home_dir) > 6 and home_dir in content:
                return {
                    "decision": "block",
                    "reason": "Rule 11 Violation: Hardcoded local workstation path detected in shared/public artifact.",
                }
    return None
