#!/usr/bin/env python3
"""
Modular PreToolUse Sentinel Dispatcher v2.0 (Clean-Room Customer Edition).
Evaluates deterministic pre-execution guardrails (<50ms) before any tool executes:
1. Destructive shell command prevention
2. Deprecated AI model rejection (Rule 28)
3. File size & binary bounds enforcement
4. Clean-room path & secret anonymization (Rule 11)
5. Control-plane self-protection (Rule 31)
6. Skill & hook deobfuscation / prompt-injection scanner
7. Zero-raw-LaTeX Google Workspace document export gate
"""

import os
import sys
import json
from typing import Dict, Any

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


def evaluate_tool_call(payload: Dict[str, Any]) -> Dict[str, Any]:
    tool_name = str(payload.get("toolName") or payload.get("tool_name") or "")
    tool_args = payload.get("toolArgs") or payload.get("tool_input") or payload.get("args") or {}
    if isinstance(tool_args, str):
        try:
            tool_args = json.loads(tool_args)
        except Exception:
            tool_args = {"raw": tool_args}

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
