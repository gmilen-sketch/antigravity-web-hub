#!/usr/bin/env python3
"""
Rule 31 Control-Plane Self-Protection Gate (Clean-Room Edition).
Blocks autonomous agent mutations to hooks.json, mcp_config.json, mcp.json,
or the active hook enforcement scripts unless explicitly authorized.
"""
import os
import re
from typing import Dict, Any, Optional

PROTECTED_BASENAMES = {
    "hooks.json",
    "mcp_config.json",
    "mcp.json",
    "sentinel_dispatch.py",
    "agent_stop_black_hat_gate.py",
    "r31_hook_integrity_guard.py",
}


def check(tool_name: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if os.environ.get("ANTIGRAVITY_ALLOW_HOOK_ADMIN") == "1":
        return None
    if tool_name in ("write_to_file", "replace_file_content"):
        target = str(tool_args.get("TargetFile", ""))
        base = os.path.basename(target)
        if base in PROTECTED_BASENAMES:
            return {
                "decision": "ask",
                "reason": f"Control-Plane Integrity Guard: Modifying protected control-plane file '{base}' requires human confirmation.",
            }
    elif tool_name == "run_command":
        cmd = str(tool_args.get("CommandLine", ""))
        for b in PROTECTED_BASENAMES:
            if re.search(r"(>|>>|\brm\b|\bmv\b|\bsed\s+-i|\btee\b).*" + re.escape(b), cmd):
                return {
                    "decision": "ask",
                    "reason": f"Control-Plane Integrity Guard: Shell mutation targeting protected file '{b}' requires confirmation.",
                }
    return None
