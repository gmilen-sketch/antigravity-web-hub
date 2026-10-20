#!/usr/bin/env python3
"""
Modular PreToolUse Sentinel Dispatcher v2.1 (Clean-Room Customer Edition).
Evaluates deterministic pre-execution guardrails (<50ms) before any tool executes:
1. Destructive shell command prevention
2. Deprecated AI model rejection (Rule 28)
3. File size & binary bounds enforcement
4. Clean-room path & secret anonymization (Rule 11)
5. Control-plane self-protection (Rule 31)
6. Skill & hook deobfuscation / prompt-injection scanner
7. Zero-raw-LaTeX Google Workspace document export gate
8. Recurring cron `IsDaemon=True` livelock guard & own-session transcript/scratch read allowlist
"""

import os
import sys
import json
from typing import Dict, Any, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from rules import (
    destructive_commands,
    deprecated_models,
    file_bounds,
    rule_11_anonymization,
    r31_hook_integrity_guard,
    audit_skill_hook_safety,
    zero_latex,
)

RULE_MODULES = [
    destructive_commands,
    deprecated_models,
    file_bounds,
    rule_11_anonymization,
    r31_hook_integrity_guard,
    audit_skill_hook_safety,
    zero_latex,
]


def check_schedule_cron_daemon_guard(tool_name: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Blocks unbounded recurring CronExpression schedules that omit both IsDaemon=True and MaxIterations."""
    if tool_name != "schedule" or not isinstance(tool_args, dict):
        return None
    cron_expr = str(tool_args.get("CronExpression") or "").strip()
    if not cron_expr:
        return None
    is_daemon = bool(tool_args.get("IsDaemon") is True)
    max_iter = tool_args.get("MaxIterations")
    has_bounded_iter = isinstance(max_iter, int) and max_iter > 0
    if not is_daemon and not has_bounded_iter:
        return {
            "decision": "deny",
            "reason": (
                "Schedule Livelock Guard: Recurring CronExpression schedules must set "
                "IsDaemon=True (for standing jobs) or a positive MaxIterations bound "
                "so the parent session or subagent can terminate cleanly."
            ),
        }
    return None


def check_own_session_transcript_access(
    tool_name: str, tool_args: Dict[str, Any], root_conversation_id: str = ""
) -> Optional[Dict[str, str]]:
    """Allows reading own-session transcript/scratch files while blocking cross-session transcript exfiltration."""
    if tool_name not in ("view_file", "read_file") or not isinstance(tool_args, dict):
        return None
    target = str(
        tool_args.get("TargetFile")
        or tool_args.get("AbsolutePath")
        or tool_args.get("Path")
        or tool_args.get("file_path")
        or ""
    ).strip()
    if not target or "transcript" not in target:
        return None
    if root_conversation_id and root_conversation_id in target:
        return {"decision": "allow"}
    return None


def evaluate_tool_call(payload: Dict[str, Any]) -> Dict[str, Any]:
    norm_payload = normalize_hook_payload(payload)
    tool_name = str(norm_payload.get("toolName") or norm_payload.get("tool_name") or "")
    tool_args = norm_payload.get("toolArgs") or norm_payload.get("tool_input") or norm_payload.get("args") or {}
    if isinstance(tool_args, str):
        try:
            tool_args = json.loads(tool_args)
        except Exception:
            tool_args = {"raw": tool_args}

    root_cid = str(norm_payload.get("rootConversationId") or "")
    cron_res = check_schedule_cron_daemon_guard(tool_name, tool_args)
    if cron_res is not None:
        return cron_res

    own_res = check_own_session_transcript_access(tool_name, tool_args, root_cid)
    if own_res is not None:
        return own_res

    for mod in RULE_MODULES:
        res = mod.check(tool_name, tool_args)
        if res is not None:
            return res

    return {"decision": "allow"}


def normalize_hook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes hook payloads across Antigravity (toolName/toolArgs/rootConversationId) and Claude Code / generic harnesses (tool_name/tool_input/session_id)."""
    if not isinstance(payload, dict):
        return {}
    out = dict(payload)
    if "toolName" not in out and "tool_name" in out:
        out["toolName"] = out["tool_name"]
    if "toolArgs" not in out and "tool_input" in out:
        out["toolArgs"] = out["tool_input"]
    root_cid = (
        out.get("rootConversationId")
        or out.get("root_conversation_id")
        or out.get("conversationId")
        or out.get("conversation_id")
        or out.get("session_id")
        or ""
    )
    if root_cid:
        out["rootConversationId"] = str(root_cid)
    return out


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    result = evaluate_tool_call(payload)
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
