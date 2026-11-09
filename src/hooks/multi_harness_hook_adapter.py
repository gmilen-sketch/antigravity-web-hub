#!/usr/bin/env python3
"""Universal Multi-Harness Hook Adapter (v1.4 Clean-Room Edition).

Role:
  Cross-Harness Lifecycle Hook Translator (`src/hooks/multi_harness_hook_adapter.py`).

Purpose:
  Bridges Antigravity Core 2.29+ / CLI 1.5+ (`PreInvocation`, `PostInvocation`,
  `PreToolUse`, `Stop`) and non-Google harnesses such as Claude Code
  (`UserPromptSubmit`, `PreToolUse`, `Stop`), Cursor, and Windsurf to the 4
  deterministic autonomy hooks (`kg_pre_invocation_hook.py`,
  `black_hat_in_progress_ux_hook.py`, `sentinel_dispatch.py`, and
  `agent_stop_black_hat_gate.py`). Emits non-deprecated `HookSystemMessage`
  (`systemMessage.systemMessage`) for Antigravity while populating
  `hookSpecificOutput.additionalContext` for Claude Code compatibility.

How It Is Used:
  - CLI entrypoint: `python3 -B src/hooks/multi_harness_hook_adapter.py --event <PreInvocation|PostInvocation|PreToolUse|Stop>`
  - Imported in unit tests (`tests/test_autonomy_kg_hooks.py`).
"""

import json
import os
import resource
import subprocess
import sys
from typing import Any, Dict, List

sys.dont_write_bytecode = True

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
CHILD_RLIMIT_AS_BYTES = 24 * 1024 * 1024 * 1024  # 24 GiB virtual address space guard

TOOL_NAME_MAP = {
    "Bash": "run_command",
    "bash": "run_command",
    "Write": "write_file",
    "Edit": "edit_file",
    "MultiEdit": "edit_file",
    "Read": "read_file",
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
    """Translates Antigravity / Claude Code PreToolUse payload to Sentinel Dispatcher and back."""
    nested = raw_payload.get("toolCall") if isinstance(raw_payload.get("toolCall"), dict) else {}
    tool_name = (
        raw_payload.get("toolName")
        or raw_payload.get("tool_name")
        or nested.get("name")
        or ""
    )
    tool_args = (
        raw_payload.get("toolArgs")
        or raw_payload.get("tool_input")
        or nested.get("args")
        or {}
    )
    mapped_tool = TOOL_NAME_MAP.get(tool_name, tool_name)
    norm_args = dict(tool_args) if isinstance(tool_args, dict) else {}
    if mapped_tool == "run_command" and "command" in norm_args and "CommandLine" not in norm_args:
        norm_args["CommandLine"] = norm_args["command"]
    elif mapped_tool in ("read_file", "write_file", "edit_file") and "file_path" in norm_args and "Path" not in norm_args:
        norm_args["Path"] = norm_args["file_path"]

    agy_payload = {
        "toolName": mapped_tool,
        "toolArgs": norm_args,
        "agentName": raw_payload.get("agentName") or raw_payload.get("agent_name") or "",
        "conversationId": raw_payload.get("conversationId") or raw_payload.get("conversation_id") or "",
        "transcriptPath": raw_payload.get("transcriptPath") or raw_payload.get("transcript_path") or "",
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
    claude_perm = "allow" if decision == "allow" else ("ask" if decision in ("ask", "force_ask") else "deny")
    out: Dict[str, Any] = {
        "decision": decision,
        "rootConversationId": agy_payload["rootConversationId"],
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": claude_perm,
        },
    }
    if "overwrite" in res and isinstance(res["overwrite"], dict):
        out["overwrite"] = res["overwrite"]
    if reason:
        out["reason"] = reason
        out["hookSpecificOutput"]["permissionDecisionReason"] = reason
    return out


def extract_injected_message_text(step: Dict[str, Any]) -> str:
    """Extracts grounding prose from HookSystemMessage (`systemMessage`), legacy `ephemeralMessage`, or an `injectSteps` envelope."""
    if not isinstance(step, dict):
        return ""
    if isinstance(step.get("injectSteps"), list) and step["injectSteps"]:
        first = step["injectSteps"][0]
        if isinstance(first, dict):
            step = first
    sm = step.get("systemMessage")
    if isinstance(sm, dict) and isinstance(sm.get("systemMessage"), str):
        return sm["systemMessage"]
    if isinstance(sm, str):
        return sm
    em = step.get("ephemeralMessage")
    return em if isinstance(em, str) else ""


def adapt_pre_invocation(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translates Antigravity PreInvocation or Claude Code UserPromptSubmit to KG grounding."""
    from kg_pre_invocation_hook import extract_root_conversation_id, run_pre_invocation_grounding

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
        cwd=str(raw_payload.get("cwd") or ""),
    )
    msg_txt = grounding.get("system_message") or grounding.get("ephemeral_message") or ""
    out: Dict[str, Any] = {
        "decision": "allow",
        "rootConversationId": root_cid,
        "matched_skills": grounding.get("matched_skills", []),
        "pinned_entities_count": len(grounding.get("pinned_entities", [])),
    }
    if msg_txt:
        out["injectSteps"] = [{"systemMessage": {"systemMessage": msg_txt}}]
        out["hookSpecificOutput"] = {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": msg_txt,
        }
    return out


def adapt_post_invocation(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Forwards Antigravity PostInvocation payload to Black-Hat UX progress controller."""
    from black_hat_in_progress_ux_hook import evaluate_post_invocation

    return evaluate_post_invocation(raw_payload)


def adapt_stop(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translates Antigravity or Claude Code Stop hook payload to Black-Hat Gate v4.18."""
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
    elif mode in ("post-invocation", "PostInvocation"):
        out = adapt_post_invocation(payload)
    elif mode in ("stop", "Stop"):
        out = adapt_stop(payload)
    else:
        out = {"decision": "allow"}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
