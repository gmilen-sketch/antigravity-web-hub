#!/usr/bin/env python3
"""
Black-Hat Critic Stop Gate (v3.0 - Clean-Room Standalone Edition).

Antigravity / Jetski `Stop` lifecycle hook. Forces the agent to run an independent
adversarial verification pass before it is allowed to end a turn in which it mutated
durable state or declared completion.

Design invariants:
  1. TURN SCOPE      - evidence is read only from the current turn (steps after the
                       last USER_INPUT / USER_EXPLICIT entry).
  2. DEFAULT-DENY    - triggered by durable state mutation (file writes outside scratch/tmp,
                       mutating shell commands, non-readonly MCP calls) or completion claims.
  3. STRUCTURAL PROOF- cleared only by an `invoke_subagent` call targeting
                       `black-hat-critic` whose own spawned transcript on disk exhibits
                       >= 2 tool steps, >= 2 model steps, and `CRITIC_VERDICT: APPROVED`.
  4. BOUNDED         - self-throttles at MAX_FORCED_CONTINUATIONS = 2.
  5. NON-RECURSIVE   - never gates the critic subagent itself or exempt terminations.
  6. AUDITABLE       - logs every decision to black_hat_gate.jsonl.
"""

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

MAX_FORCED_CONTINUATIONS = 2
CRITIC_AGENT_NAME = "black-hat-critic"

DATA_DIR = os.path.expanduser(os.environ.get("ANTIGRAVITY_DATA_DIR", "~/.gemini/antigravity"))
LOG_PATH = os.path.join(DATA_DIR, "logs", "black_hat_gate.jsonl")

BRAIN_CANDIDATES = [
    os.path.join(DATA_DIR, "brain"),
    os.path.expanduser("~/.gemini/antigravity/brain"),
    os.path.expanduser("~/.gemini/jetski/brain"),
    "/mnt/data/.gemini/antigravity/brain",
]

NON_GATED_TERMINATIONS = {
    "ERROR",
    "USER_CANCELED",
    "MAX_INVOCATIONS",
    "MAX_FORCED_INVOCATIONS",
    "MAX_TOKEN_BUDGET_EXCEEDED",
    "EARLY_CONTINUE",
    "INJECTED_RESPONSE",
    "TERMINAL_CUSTOM_HOOK",
}

NON_GATED_AGENTS = {
    CRITIC_AGENT_NAME,
    "black_hat_critic",
    "research-agent",
    "custom_subagent",
}

MUTATING_TOOLS = {
    "write_to_file",
    "replace_file_content",
    "notebook_edit",
    "edit_file",
    "create_file",
}

TARGET_KEYS = ("TargetFile", "AbsolutePath", "NotebookPath", "path", "file_path")

MUTATING_COMMAND_PATTERNS = [
    r"(^|[;&|]\s*)(rm|mv|cp|mkdir|rmdir|chmod|chown|ln|touch|truncate)\s",
    r"\btee\b",
    r"\bsed\s+-i\b",
    r"\bgit\s+(add|commit|push|merge|rebase|tag|reset|checkout\s+-b)\b",
    r"\b(pip|pip3|npm|yarn|apt|apt-get)\s+(install|uninstall|remove|publish)\b",
    r"\bgcloud\s+\S+\s+(create|delete|update|deploy|set|add|remove|import)\b",
    r"\bcurl\b[^|;]*-X\s*(POST|PUT|PATCH|DELETE)",
    r"\bkubectl\s+(apply|delete|create|patch|scale)\b",
    r"\bterraform\s+(apply|destroy)\b",
    r"[^>]>>?\s*[^\s|&]+",
]

READONLY_MCP_PREFIXES = (
    "get_", "get", "list_", "list", "search_", "search", "read_", "read",
    "fetch_", "fetch", "query_", "render_", "describe_", "view_", "lookup_",
    "find_", "discover_", "explain_", "similar_", "inspect_", "batch_get",
    "ask_", "count_", "show_", "status",
)

READONLY_MCP_MARKERS = ("readonly", "read_only", "_status", "_detail", "_summary")

COMPLETION_PATTERNS = [
    r"\b(i(?:'|\u2019)?m? (?:am )?(?:done|finished|all set))\b",
    r"\b(tests?|suites?)\s+(?:are|is)?\s*(?:ready|passing|passed|green|verified)\b",
    r"\ball\s+(?:tests?|suites?|checks?)\s+pass(?:ed|ing)?\b",
    r"\bverification\s+(?:is\s+)?complete(?:d)?\b",
    r"\bverified\s+and\s+(?:done|complete|passed)\b",
    r"\b(task|milestone|ticket|workflow|step|sync|migration|audit|sweep|rollout)\s+"
    r"(?:is\s+)?(?:complete|completed|done|finished|resolved|fixed|green)\b",
    r"\bstatus:\s*['\"]?(?:COMPLETED|DONE|RESOLVED|FIXED|SUCCESS|PASSED|CLOSED)\b",
    r"\bverdict\s*[:\-]?\s*\**\s*(pass(?:ed)?|approved|complete(?:d)?|green)\b",
]

APPROVED_VERDICT = re.compile(r"CRITIC_VERDICT\s*[:=]\s*APPROVED", re.IGNORECASE)
REJECTED_VERDICT = re.compile(r"CRITIC_VERDICT\s*[:=]\s*REJECTED", re.IGNORECASE)

MODEL_PROSE_TYPES = {"PLANNER_RESPONSE"}


def read_payload() -> Dict[str, Any]:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("stopHookArgs") or payload.get("stop_hook_args")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update({k: v for k, v in payload.items() if k != "stopHookArgs"})
        return merged
    return payload


def get_str(payload: Dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        val = payload.get(key)
        if isinstance(val, str) and val:
            return val
    return default


def get_int(payload: Dict[str, Any], *keys: str, default: int = 0) -> int:
    for key in keys:
        val = payload.get(key)
        if isinstance(val, bool):
            continue
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return default


def load_steps(transcript_path: str) -> List[Dict[str, Any]]:
    if not transcript_path or not os.path.exists(transcript_path):
        return []
    steps: List[Dict[str, Any]] = []
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if isinstance(entry, dict):
                        steps.append(entry)
                except Exception:
                    continue
    except Exception:
        return []
    return steps


def slice_current_turn(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    start = 0
    for idx, entry in enumerate(steps):
        if entry.get("type") == "USER_INPUT" and entry.get("source") == "USER_EXPLICIT":
            start = idx + 1
    return steps[start:]


def first_user_input(steps: List[Dict[str, Any]]) -> str:
    for entry in steps:
        if entry.get("type") == "USER_INPUT":
            return str(entry.get("content") or "")
    return ""


def iter_tool_calls(turn: List[Dict[str, Any]]):
    for entry in turn:
        for call in entry.get("tool_calls") or []:
            if isinstance(call, dict):
                yield call.get("name") or "", call.get("args") or {}


def final_model_text(turn: List[Dict[str, Any]], fallback: str = "") -> str:
    text = ""
    for entry in turn:
        if entry.get("type") in MODEL_PROSE_TYPES and entry.get("content"):
            text = str(entry["content"])
    return text or fallback


def _normalize(path: str) -> str:
    if not path:
        return ""
    expanded = os.path.expanduser(os.path.expandvars(path))
    if not os.path.isabs(expanded):
        expanded = os.path.abspath(expanded)
    try:
        return os.path.realpath(os.path.normpath(expanded))
    except Exception:
        return os.path.normpath(expanded)


def _is_within(child: str, parent: str) -> bool:
    if not child or not parent:
        return False
    child = _normalize(child)
    parent = _normalize(parent)
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


def is_exempt_target(target: str, artifact_dir: str) -> bool:
    if not target:
        return False
    normalized = _normalize(target)
    if not normalized:
        return False
    for exempt_root in ("/tmp", "/dev/shm"):
        if _is_within(normalized, exempt_root):
            return True
    if artifact_dir and _is_within(normalized, os.path.join(artifact_dir, "scratch")):
        return True
    if normalized == _normalize(LOG_PATH):
        return True
    return False


def is_mutating_command(command: str) -> bool:
    for pattern in MUTATING_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def is_mutating_mcp(tool_name: str, args: Dict[str, Any]) -> bool:
    raw = (tool_name or "").lower()
    if raw == "call_mcp_tool":
        name = str(args.get("ToolName") or "").lower()
    elif raw.startswith("mcp_"):
        parts = raw.split("_", 2)
        name = parts[2] if len(parts) > 2 else ""
    else:
        return False
    if not name:
        return True
    if any(marker in name for marker in READONLY_MCP_MARKERS):
        return False
    return not name.startswith(READONLY_MCP_PREFIXES)


def detect_mutations(turn: List[Dict[str, Any]], artifact_dir: str) -> List[str]:
    mutations: List[str] = []
    for name, args in iter_tool_calls(turn):
        if not isinstance(args, dict):
            args = {}
        if name in MUTATING_TOOLS:
            target = ""
            for key in TARGET_KEYS:
                if isinstance(args.get(key), str):
                    target = args[key]
                    break
            if not is_exempt_target(target, artifact_dir):
                mutations.append(f"{name} -> {target or '<unknown target>'}")
            continue
        if name == "run_command":
            command = str(args.get("CommandLine") or "")
            if is_mutating_command(command):
                mutations.append(f"run_command -> {command[:120]}")
            continue
        if is_mutating_mcp(name, args):
            detail = args.get("ToolName") or name
            mutations.append(f"mcp write -> {detail}")
    return mutations


def detect_completion_claim(text: str) -> Optional[str]:
    if not text:
        return None
    for pattern in COMPLETION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(0)[:80]
    return None


def critic_typenames(args: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    if not isinstance(args, dict):
        return names
    subagents = args.get("Subagents")
    if isinstance(subagents, list):
        for entry in subagents:
            if isinstance(entry, dict) and isinstance(entry.get("TypeName"), str):
                names.append(entry["TypeName"].strip().lower())
    if isinstance(args.get("TypeName"), str):
        names.append(args["TypeName"].strip().lower())
    return names


def extract_conversation_ids(text: str) -> List[str]:
    return re.findall(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        text or "",
        re.IGNORECASE,
    )


def read_subagent_verdict(conversation_id: str) -> Tuple[Optional[str], str]:
    path = ""
    for root in BRAIN_CANDIDATES:
        base = os.path.join(root, conversation_id)
        for candidate in (
            os.path.join(base, ".system_generated", "logs", "transcript_full.jsonl"),
            os.path.join(base, ".system_generated", "logs", "transcript.jsonl"),
        ):
            if os.path.exists(candidate):
                path = candidate
                break
        if path:
            break
    if not path:
        return None, f"spawned critic {conversation_id[:8]} has no transcript file"

    model_steps = 0
    tool_steps = 0
    approved = False
    rejected = False
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") in MODEL_PROSE_TYPES:
                    model_steps += 1
                    content = str(entry.get("content") or "")
                    if REJECTED_VERDICT.search(content):
                        rejected = True
                    elif APPROVED_VERDICT.search(content):
                        approved = True
                if entry.get("tool_calls"):
                    tool_steps += 1
    except Exception as exc:
        return None, f"critic transcript unreadable: {exc!r}"

    if tool_steps < 2 or model_steps < 2:
        return None, (
            f"critic {conversation_id[:8]} transcript shows insufficient audit activity "
            f"({tool_steps} tool steps, {model_steps} model steps)"
        )
    if rejected:
        return "REJECTED", f"critic {conversation_id[:8]} returned CRITIC_VERDICT: REJECTED"
    if approved:
        return "APPROVED", f"critic {conversation_id[:8]} returned CRITIC_VERDICT: APPROVED"
    return None, f"critic {conversation_id[:8]} produced no verdict"


def find_structural_proof(turn: List[Dict[str, Any]]) -> Tuple[bool, str]:
    spawn_ids: List[str] = []
    invoked = False
    for idx, entry in enumerate(turn):
        critic_call = False
        for call in entry.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            if call.get("name") == "invoke_subagent" and CRITIC_AGENT_NAME in critic_typenames(
                call.get("args") or {}
            ):
                critic_call = True
        if not critic_call:
            continue
        invoked = True
        for result in turn[idx + 1:]:
            if result.get("type") in MODEL_PROSE_TYPES:
                continue
            content = str(result.get("content") or "")
            if "conversationid" in content.lower():
                spawn_ids.extend(cid.lower() for cid in extract_conversation_ids(content))
            break

    if not invoked:
        return False, "no independent verification executed in this turn"
    if not spawn_ids:
        return False, "critic subagent invoked but no spawn result with a conversation id"

    verdicts: List[Tuple[Optional[str], str]] = [
        read_subagent_verdict(cid) for cid in dict.fromkeys(spawn_ids)
    ]
    for verdict, detail in reversed(verdicts):
        if verdict == "APPROVED":
            return True, detail
        if verdict == "REJECTED":
            return False, detail
    return False, verdicts[-1][1] if verdicts else "critic produced no verdict"


def rejection_text(mutations: List[str], claim: Optional[str], proof_detail: str) -> str:
    listed = "\n".join(f"   - {m}" for m in mutations[:8]) or "   - (none)"
    claim_line = f"Completion claim detected: \"{claim}\"\n" if claim else ""
    return (
        "🛑 BLACK-HAT CRITIC GATE: independent verification missing.\n\n"
        f"{claim_line}"
        f"State mutated in this turn:\n{listed}\n\n"
        f"Gate status: {proof_detail}.\n\n"
        "Clear this gate by invoking:\n"
        f"  invoke_subagent(TypeName=\"{CRITIC_AGENT_NAME}\") with deliverable paths, "
        "commands executed, and claims to verify. The critic must independently inspect "
        "on-disk state and emit `CRITIC_VERDICT: APPROVED` or `CRITIC_VERDICT: REJECTED`."
    )


def evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
    reason_code = get_str(payload, "terminationReason", "termination_reason").upper()
    reason_code = reason_code.replace("EXECUTOR_TERMINATION_REASON_", "")
    agent_name = get_str(payload, "agentName", "agent_name").lower()
    execution_num = get_int(payload, "executionNum", "execution_num")
    transcript_path = get_str(payload, "transcriptPath", "transcript_path")
    artifact_dir = get_str(payload, "artifactDirectoryPath", "artifact_directory_path")
    fully_idle = payload.get("fullyIdle", payload.get("fully_idle", True))

    def allow(why: str, **extra: Any) -> Dict[str, Any]:
        out = {"decision": "allow", "audit": why}
        out.update(extra)
        return out

    if reason_code in NON_GATED_TERMINATIONS:
        return allow(f"termination reason {reason_code} is not gated")
    if agent_name in NON_GATED_AGENTS:
        return allow(f"agent {agent_name} is exempt")
    if fully_idle is False:
        return allow("dependents still running")
    if execution_num >= MAX_FORCED_CONTINUATIONS:
        return allow(
            f"continuation budget exhausted ({execution_num}/{MAX_FORCED_CONTINUATIONS})",
            budget_exhausted=True,
        )

    steps = load_steps(transcript_path)
    if not steps:
        return allow("transcript unavailable or empty")

    seed = first_user_input(steps)
    if re.search(r"black[- ]hat|CRITIC_VERDICT", seed, re.IGNORECASE):
        return allow("conversation seeded as a black-hat audit")

    turn = slice_current_turn(steps)
    if not turn:
        return allow("no steps in current turn")

    final_text = final_model_text(
        turn, fallback=get_str(payload, "finalModelOutput", "final_model_output")
    )
    if not final_text and not any(iter_tool_calls(turn)):
        return allow("no model output or tool calls in current turn")

    mutations = detect_mutations(turn, artifact_dir)
    claim = detect_completion_claim(final_text)
    if not mutations and not claim:
        return allow("read-only turn with no completion claim")

    proof_found, proof_detail = find_structural_proof(turn)
    if proof_found:
        return allow(
            f"verified: {proof_detail}",
            mutations=len(mutations),
            claim=claim,
        )

    return {
        "decision": "continue",
        "reason": rejection_text(mutations, claim, proof_detail),
        "audit": f"blocked: {proof_detail}",
        "mutations": len(mutations),
        "claim": claim,
    }


def log_record(payload: Dict[str, Any], result: Dict[str, Any], elapsed_ms: float) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "conversationId": get_str(payload, "conversationId", "conversation_id"),
            "agentName": get_str(payload, "agentName", "agent_name"),
            "terminationReason": get_str(payload, "terminationReason", "termination_reason"),
            "executionNum": get_int(payload, "executionNum", "execution_num"),
            "decision": result.get("decision"),
            "audit": result.get("audit"),
            "mutations": result.get("mutations"),
            "claim": result.get("claim"),
            "elapsed_ms": round(elapsed_ms, 1),
        }
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except Exception:
        pass


def main() -> None:
    started = time.time()
    payload = read_payload()
    try:
        result = evaluate(payload)
    except Exception as exc:
        result = {"decision": "allow", "audit": f"gate error: {exc!r}"}
    log_record(payload, result, (time.time() - started) * 1000.0)
    response = {"decision": result["decision"]}
    if result.get("reason"):
        response["reason"] = result["reason"]
    print(json.dumps(response))


if __name__ == "__main__":
    main()
