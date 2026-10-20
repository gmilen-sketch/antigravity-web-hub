#!/usr/bin/env python3
"""Universal Multi-Harness Hook Adapter (v1.3 Clean-Room Edition).

Bridges Antigravity CLI (`agy`) / Antigravity 2.0 (`PreInvocation`, `PreToolUse`, `Stop`)
and non-Google harnesses such as Claude Code (`UserPromptSubmit`, `PreToolUse`, `Stop`),
Cursor, Windsurf, and Cloud Code to the 3 core autonomy hooks:
  1. `kg_pre_invocation_hook.py` (Turn-1 Pinned KV-Cache + 2-Hop KG + 20-Skill Resolver)
  2. `sentinel_dispatch.py`      (PreToolUse Safety, OOM Guard & Parameter Sanitizer)
  3. `agent_stop_black_hat_gate.py` (2-Stage Stateless Goldfish -> Isolated Judge Stop Gate)
"""

import json
import os
import resource
import subprocess
import sys
from typing import Any, Dict, List

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
CHILD_RLIMIT_AS_BYTES = 24 * 1024 * 1024 * 1024  # 24 GiB virtual address space guard

TOOL_NAME_MAP = {
    "Bash": "run_command",
    "bash": "run_command",
    "Write": "write_to_file",
    "Edit": "replace_file_content",
    "MultiEdit": "replace_file_content",
    "Read": "view_file",
}


def apply_child_rlimit_as(max_bytes: int = CHILD_RLIMIT_AS_BYTES) -> bool:
    """Applies a 24 GiB RLIMIT_AS virtual memory ceiling to prevent runaway child OOMs."""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        new_soft = max_bytes if (soft == resource.RLIM_INFINITY or soft > max_bytes) else soft
        new_hard = max_bytes if (hard == resource.RLIM_INFINITY or hard > max_bytes) else hard
        if new_soft > new_hard:
            new_soft = new_hard
        resource.setrlimit(resource.RLIMIT_AS, (new_soft, new_hard))
        return True
    except Exception:
        return False


def adapt_pre_tool_use(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translates Claude Code / generic PreToolUse payload to Sentinel Dispatcher and back."""
    tool_name = raw_payload.get("toolName") or raw_payload.get("tool_name") or ""
    tool_args = raw_payload.get("toolArgs") or raw_payload.get("tool_input") or {}
    mapped_tool = TOOL_NAME_MAP.get(tool_name, tool_name)
    norm_args = dict(tool_args) if isinstance(tool_args, dict) else {}
    if "command" in norm_args and "CommandLine" not in norm_args:
        norm_args["CommandLine"] = norm_args["command"]
    if "file_path" in norm_args and "TargetFile" not in norm_args:
        norm_args["TargetFile"] = norm_args["file_path"]

    agy_payload = {
        "toolName": mapped_tool,
        "toolArgs": norm_args,
        "rootConversationId": (
            raw_payload.get("rootConversationId")
            or raw_payload.get("conversationId")
            or raw_payload.get("session_id")
            or "multi-harness-session"
        ),
    }
    proc = subprocess.run(
        [sys.executable, "-B", os.path.join(HOOKS_DIR, "sentinel_dispatch.py")],
        input=json.dumps(agy_payload),
        text=True,
        capture_output=True,
        preexec_fn=lambda: apply_child_rlimit_as(CHILD_RLIMIT_AS_BYTES),
    )
    try:
        res = json.loads(proc.stdout.strip()) if proc.stdout.strip() else {"decision": "allow"}
    except Exception:
        res = {"decision": "allow"}

    decision = res.get("decision", "allow")
    reason = res.get("reason") or res.get("message") or ""
    claude_perm = "allow" if decision == "allow" else ("ask" if decision == "ask" else "deny")
    out: Dict[str, Any] = {
        "decision": decision,
        "rootConversationId": agy_payload["rootConversationId"],
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": claude_perm,
        },
    }
    if reason:
        out["reason"] = reason
        out["hookSpecificOutput"]["permissionDecisionReason"] = reason
    return out


def adapt_pre_invocation(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translates Antigravity PreInvocation or Claude Code UserPromptSubmit to KG grounding."""
    from kg_pre_invocation_hook import run_pre_invocation_grounding, extract_root_conversation_id

    root_cid = extract_root_conversation_id(raw_payload)
    prompt_text = str(
        raw_payload.get("prompt")
        or raw_payload.get("user_prompt")
        or raw_payload.get("query")
        or ""
    )
    grounding = run_pre_invocation_grounding(
        prompt_text=prompt_text,
        session_id=str(raw_payload.get("session_id") or root_cid),
        root_conversation_id=root_cid,
    )
    ephemeral = grounding.get("ephemeral_message", "")
    out: Dict[str, Any] = {
        "decision": "allow",
        "rootConversationId": root_cid,
        "matched_skills": grounding.get("matched_skills", []),
        "pinned_entities_count": len(grounding.get("pinned_entities", [])),
    }
    if ephemeral:
        out["injectSteps"] = [{"ephemeralMessage": ephemeral}]
        out["hookSpecificOutput"] = {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": ephemeral,
        }
    return out


def adapt_stop(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translates Antigravity or Claude Code Stop hook payload to Black-Hat Gate v4.9."""
    from agent_stop_black_hat_gate import evaluate

    if raw_payload.get("stop_hook_active") is True:
        return {"decision": "allow", "audit": "stop_hook_active guard prevented infinite loop"}

    res = evaluate(raw_payload)
    decision = res.get("decision", "allow")
    out: Dict[str, Any] = {
        "decision": decision,
        "audit": res.get("audit", ""),
        "rootConversationId": res.get("rootConversationId", ""),
    }
    if decision == "continue" and res.get("reason"):
        out["reason"] = res["reason"]
    return out


def _resolve_event_mode(argv: List[str]) -> str:
    """Resolves the hook event mode from `--event <mode>`, `--event=<mode>`, or positional `argv[1]`."""
    if len(argv) <= 1:
        return "pre-tool-use"
    for idx in range(1, len(argv)):
        arg = argv[idx]
        if arg == "--event" and idx + 1 < len(argv):
            return argv[idx + 1]
        if arg.startswith("--event="):
            return arg.split("=", 1)[1]
    return argv[1]


def main() -> None:
    mode = _resolve_event_mode(sys.argv)
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    if mode in ("pre-tool-use", "PreToolUse"):
        out = adapt_pre_tool_use(payload)
    elif mode in ("pre-invocation", "PreInvocation", "UserPromptSubmit"):
        out = adapt_pre_invocation(payload)
    elif mode in ("stop", "Stop"):
        out = adapt_stop(payload)
    else:
        out = {"decision": "allow"}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
