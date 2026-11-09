#!/usr/bin/env python3
"""Rule 31 Control-Plane Self-Protection Gate (`force_ask` Clean-Room Edition).

Escalates autonomous agent mutations targeting `hooks.json`, `plugin.json`,
`mcp_config.json`, `mcp.json`, or active hook enforcement scripts via
`decision = "force_ask"` (enforced even in Turbo mode) unless explicitly
authorized via `ANTIGRAVITY_ALLOW_HOOK_ADMIN=1`.
"""

import os
import re
from typing import Any, Dict, Optional

PROTECTED_BASENAMES = {
    "hooks.json",
    "mcp_config.json",
    "mcp.json",
    "sentinel_dispatch.py",
    "agent_stop_black_hat_gate.py",
    "black_hat_in_progress_ux_hook.py",
    "kg_pre_invocation_hook.py",
    "run_hook_safe.sh",
    "r31_hook_integrity_guard.py",
}

_WRITE_TOOLS = frozenset({
    "write_file",
    "edit_file",
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
})


def check(tool_name: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if os.environ.get("ANTIGRAVITY_ALLOW_HOOK_ADMIN") == "1":
        return None
    if tool_name in _WRITE_TOOLS:
        target = str(
            tool_args.get("Path")
            or tool_args.get("TargetFile")
            or tool_args.get("file_path")
            or ""
        )
        base = os.path.basename(target)
        if base in PROTECTED_BASENAMES:
            return {
                "decision": "force_ask",
                "reason": (
                    f"Control-Plane Integrity Guard: Modifying protected control-plane file "
                    f"'{base}' requires explicit human confirmation."
                ),
            }
    elif tool_name == "run_command":
        cmd = str(tool_args.get("CommandLine") or tool_args.get("command") or "")
        for b in PROTECTED_BASENAMES:
            if re.search(r"(>|>>|\brm\b|\bmv\b|\bsed\s+-i|\btee\b|\bcp\b).*" + re.escape(b), cmd):
                return {
                    "decision": "force_ask",
                    "reason": (
                        f"Control-Plane Integrity Guard: Shell mutation targeting protected file "
                        f"'{b}' requires explicit human confirmation."
                    ),
                }
    return None


check_r31_integrity = check

