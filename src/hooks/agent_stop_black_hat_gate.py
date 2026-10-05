#!/usr/bin/env python3
"""Black-Hat Critic Stop Gate (v4.3 - 2-Stage Stateless Goldfish -> Isolated Judge, Clean-Room Edition).

Antigravity `Stop` lifecycle hook. Forces the agent to run an independent adversarial
verification pass before it is allowed to end a turn in which it mutated state or
declared completion.

Design invariants (v4.3):
  1. TURN SCOPE      - evidence is read only from the current turn (everything after
                       the last USER_INPUT/USER_EXPLICIT step).
  2. DEFAULT-DENY    - triggers on durable state mutation or explicit deliverable/completion claims.
  3. STRUCTURAL PROOF- Primary route: 2-stage `black-hat-goldfish` (stateless investigator, C1-C5)
                       followed by `black-hat-judge` (isolated adjudicator reading goldfish transcript, C6-C8).
                       Fallback route: single-stage `black-hat-critic` when neither goldfish nor judge
                       was invoked (unless BH_GATE_STRICT_TWO_STAGE=1).
  4. ATTACHED CHECKS - runs in-process AST/JSON/file-size/test-facade verification on mutated files.
  5. BOTTOM SUMMARY  - enforces Compact 2-Part Bottom Summary when a substantive pre-critic response exists.
  6. BOUNDED         - self-throttles on `executionNum` at MAX_FORCED_CONTINUATIONS.
  7. NON-RECURSIVE   - never gates critic/goldfish/judge/leaf subagents.
"""

import ast
import json
import os
import py_compile
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

MAX_FORCED_CONTINUATIONS = 2

LOG_PATH = os.path.expanduser(
    os.environ.get("BLACK_HAT_GATE_LOG_PATH") or "~/.gemini/antigravity/logs/black_hat_gate.jsonl"
)

CRITIC_AGENT_NAME = "black-hat-critic"
GOLDFISH_AGENT_NAME = "black-hat-goldfish"
JUDGE_AGENT_NAME = "black-hat-judge"

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
    GOLDFISH_AGENT_NAME,
    "black_hat_goldfish",
    JUDGE_AGENT_NAME,
    "black_hat_judge",
    "research",
    "research-google",
    "custom_subagent",
    "workspace-housekeeper",
    "workspace_housekeeper",
    "dreaming-improvement-reasoner",
    "dreaming_improvement_reasoner",
    "self",
}

HANDCUFF_PROMPT_RE = re.compile(
    r"\b(use\s+`?view_file`?\s+only|view_file\s+only|do\s+not\s+run\s+(?:any\s+)?(?:shell\s+)?commands(?:\s*$|\s*[.;,)])|skip\s+`?run_command`?|without\s+running\s+commands)\b",
    re.IGNORECASE,
)

GOLDFISH_SPIN_PATTERNS = [
    r"\bphase[- ]?2\b",
    r"\bknown\s+(?:issue|flaky|item|limitation|sprint)\b",
    r"\bnon-blocking\b",
    r"\bflaky\b",
    r"\bintentional(?:ly)?\s+placeholder\b",
    r"\bcold\s+dr\b",
    r"\bstandby\b",
    r"\brolled\s+into\b",
    r"\bverified\s+this\s+in\s+turn\b",
    r"\balready\s+verified\b",
    r"\bclose\s+enough\b",
    r"\beffectively\s+done\b",
    r"\bagreed\s+to\s+defer\b",
    r"\bpre-existing\b",
    r"\bready\s+for\s+approval\b",
    r"\bquick\s+confirmation\s+is\s+enough\b",
]

FILE_MUTATING_TOOLS = {
    "write_to_file",
    "replace_file_content",
    "notebook_edit",
    "edit_file",
    "create_file",
}

MUTATING_TOOLS = FILE_MUTATING_TOOLS | {
    "generate_image",
}

TARGET_KEYS = ("TargetFile", "AbsolutePath", "NotebookPath", "path", "file_path", "ImageName")

MUTATING_COMMAND_PATTERNS = [
    r"(^|[;&|]\s*)(rm|mv|cp|mkdir|rmdir|chmod|chown|ln|touch|truncate)\s",
    r"\btee\b",
    r"\bsed\s+-i\b",
    r"\bgit\s+(add|commit|push|merge|rebase|tag|reset|checkout\s+-b)\b",
    r"\b(pip|pip3|npm|yarn|apt|apt-get|gem)\s+(install|uninstall|remove|publish)\b",
    r"\bgcloud\s+\S+\s+(create|delete|update|deploy|set|add|remove|import)\b",
    r"\bbq\s+(load|mk|rm|insert|update)\b",
    r"\bgsutil\s+(cp|rm|mv|rsync)\b",
    r"\bcurl\b[^|;]*-X\s*(POST|PUT|PATCH|DELETE)",
    r"\bkubectl\s+(apply|delete|create|patch|scale)\b",
    r"\bterraform\s+(apply|destroy)\b",
    r"\b(diagram[-_]renderer|mmdc)\b",
    r"(?<![>-])>>?\s*[^\s|&]+",
]

READONLY_MCP_PREFIXES = (
    "get_",
    "get",
    "list_",
    "list",
    "search_",
    "search",
    "read_",
    "read",
    "fetch_",
    "fetch",
    "query_",
    "render_",
    "describe_",
    "view_",
    "lookup_",
    "find_",
    "discover_",
    "explain_",
    "similar_",
    "inspect_",
    "batch_get",
    "ask_",
    "count_",
    "show_",
    "status",
    "kg_search",
    "kg_get",
)

READONLY_MCP_MARKERS = ("readonly", "read_only", "_status", "_detail", "_summary")

DELIVERABLE_CREATION_PATTERNS = [
    r"\b(i\s+have\s+|we\s+have\s+)?(created|generated|produced|wrote|written|updated|modified|patched|committed|pushed|published|exported|rendered)\s+(?:the\s+|a\s+|an\s+|all\s+)?(?:new\s+|updated\s+|requested\s+|final\s+)?(deliverables?|artifacts?|reports?|documents?|spreadsheets?|sheets?|slides?|diagrams?|scripts?|files?|commits?|fixes?|patches?|implementations?|architectures?)\b",
    r"\b(deliverables?|artifacts?|reports?|documents?|spreadsheets?|files?|scripts?|changes?|fixes?|patches?)\s+(?:have\s+been|has\s+been|were|was|is\s+now|are\s+now)\s+(created|generated|produced|written|saved|updated|committed|pushed|delivered|exported|rendered)\b",
    r"\bledger\s+updated\b",
    r"\bsync\s+complete(?:d)?\b",
    r"\b(delivered|transmitted|dispatched|reported)\s+to\s+(?:the\s+)?(parent|caller|orchestrator|user|team|space)\b",
]

COMPLETION_PATTERNS = DELIVERABLE_CREATION_PATTERNS + [
    r"\b(i(?:'|\u2019)?m? (?:am )?(?:done|finished|all set))\b",
    r"\b(tests?|suites?)\s+(?:are|is)?\s*(?:passing|passed|green|verified)\b",
    r"\ball\s+(?:tests?|suites?|checks?)\s+pass(?:ed|ing)?\b",
    r"\bverification\s+(?:is\s+)?complete(?:d)?\b",
    r"\bverified\s+and\s+(?:done|complete|passed)\b",
    r"\b(task|milestone|ticket|workflow|step|sync|migration|audit|sweep|rollout|deliverable|artifact|implementation|refactor)\s+"
    r"(?:is\s+)?(?:complete|completed|done|finished|resolved|fixed|green|delivered|produced)\b",
    r"\bstatus:\s*['\"]?(?:COMPLETED|DONE|RESOLVED|FIXED|SUCCESS|PASSED|CLOSED)\b",
    r"\b(marked|marking|updated)\b[^.\n]{0,60}\b(as\s+)?(complete|completed|done|fixed|closed)\b",
    r"\b(deliverable|artifact|pr|branch|patch|fix|implementation)\s+is\s+ready\s+(?:for|to)\s+(?:next|subsequent|deploy|test|review|proceed|execute|merge|submit)\b",
    r"\bverdict\s*[:\-]?\s*\**\s*(pass(?:ed)?|approved|complete(?:d)?|green)\b",
    r"\b\d+\s*/\s*\d+\s+(checks?|tests?|assertions?|files?|rows?)\s+(pass(?:ed)?|verified|migrated|updated)\b",
    r"^#{2,4}\s*(?:Fixes Executed|Execution Complete|Production Verification Run|Deliverables Produced)\b",
]

APPROVED_VERDICT = re.compile(r"CRITIC_VERDICT\s*[:=]\s*APPROVED", re.IGNORECASE)
REJECTED_VERDICT = re.compile(r"CRITIC_VERDICT\s*[:=]\s*REJECTED", re.IGNORECASE)

BRAIN_CANDIDATE_ROOTS = [
    os.path.expanduser("~/.gemini/antigravity/brain"),
    "/mnt/data/.gemini/antigravity/brain",
]

MODEL_PROSE_TYPES = {"PLANNER_RESPONSE"}
TOOL_RESULT_TYPES = {"GENERIC", "EPHEMERAL_MESSAGE", "SYSTEM_MESSAGE", "TOOL_RESULT"}


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
        for key in ("terminationReason", "executionNum", "fullyIdle", "finalModelOutput"):
            if key not in payload and key in nested:
                merged[key] = nested[key]
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
    if not transcript_path:
        return []
    if transcript_path.endswith("transcript.jsonl"):
        full_candidate = os.path.join(os.path.dirname(transcript_path), "transcript_full.jsonl")
        if os.path.exists(full_candidate):
            transcript_path = full_candidate
    if not os.path.exists(transcript_path):
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
                except Exception:
                    continue
                if isinstance(entry, dict):
                    steps.append(entry)
    except Exception:
        return []
    return steps


def slice_current_turn(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    start = 0
    found_explicit = False
    for idx, entry in enumerate(steps):
        if entry.get("type") == "USER_INPUT" and entry.get("source") == "USER_EXPLICIT":
            start = idx + 1
            found_explicit = True
    if not found_explicit:
        for idx, entry in enumerate(steps):
            if entry.get("type") == "USER_INPUT":
                start = idx + 1
    return steps[start:]


def first_user_input(steps: List[Dict[str, Any]]) -> str:
    for entry in steps:
        if entry.get("type") == "USER_INPUT":
            return str(entry.get("content") or "")
    return ""


def current_turn_user_input(steps: List[Dict[str, Any]]) -> str:
    last_text = ""
    for entry in steps:
        if entry.get("type") == "USER_INPUT" and entry.get("source") == "USER_EXPLICIT":
            last_text = str(entry.get("content") or "")
    if not last_text:
        for entry in steps:
            if entry.get("type") == "USER_INPUT":
                last_text = str(entry.get("content") or "")
    return last_text or first_user_input(steps)


def _decode_arg_value(val: Any) -> Any:
    if isinstance(val, str) and len(val) >= 2 and (
        val[0] in ('"', "[", "{") or val in ("true", "false", "null")
    ):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


def _decode_args(raw_args: Any) -> Dict[str, Any]:
    if not isinstance(raw_args, dict):
        return {}
    return {k: _decode_arg_value(v) for k, v in raw_args.items()}


def _entry_model_text(entry: Dict[str, Any]) -> str:
    parts: List[str] = []
    if entry.get("content"):
        parts.append(str(entry["content"]))
    for call in entry.get("tool_calls") or []:
        if isinstance(call, dict) and call.get("name") == "send_message":
            msg = _decode_args(call.get("args")).get("Message")
            if isinstance(msg, str) and msg:
                parts.append(msg)
    return "\n".join(parts)


def iter_tool_calls(turn: List[Dict[str, Any]]):
    for entry in turn:
        for call in entry.get("tool_calls") or []:
            if isinstance(call, dict):
                yield call.get("name") or "", _decode_args(call.get("args"))


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


def detect_deliverable_claim(text: str) -> Optional[str]:
    if not text:
        return None
    for pattern in DELIVERABLE_CREATION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(0)[:80]
    return None


def detect_completion_claim(text: str) -> Optional[str]:
    if not text:
        return None
    for pattern in COMPLETION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(0)[:80]
    return None


def is_simple_question_turn(
    steps: List[Dict[str, Any]], mutations: List[str], final_text: str
) -> bool:
    if mutations:
        return False
    if detect_deliverable_claim(final_text):
        return False
    user_text = current_turn_user_input(steps).strip()
    if not user_text:
        return False
    is_question_form = bool(
        "?" in user_text
        or re.search(
            r"^\s*(what|which|who|where|when|why|how|is|are|can\s+you\s+explain|explain|tell\s+me|describe|list|show\s+me|check\s+why|let'?s\s+start\s+planning|plan|planning|review|summarize|compare|brainstorm)\b",
            user_text,
            re.IGNORECASE,
        )
    )
    if not is_question_form:
        return False
    has_mutation_imperative = bool(
        re.search(
            r"\b(create|write|build|implement|update|edit|modify|fix|patch|generate|produce|commit|push|submit|delete|remove|sync|refactor|deploy)\b",
            user_text,
            re.IGNORECASE,
        )
    )
    return not has_mutation_imperative


def critic_typenames(args: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    args = _decode_args(args)
    if not args:
        return names
    subagents = args.get("Subagents")
    if isinstance(subagents, str):
        try:
            subagents = json.loads(subagents)
        except Exception:
            for m in re.finditer(r'"TypeName"\s*:\s*"([^"]+)"', subagents):
                names.append(m.group(1).strip().lower())
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


def _resolve_subagent_transcript(conversation_id: str, label: str = "critic") -> Tuple[str, str]:
    for root in BRAIN_CANDIDATE_ROOTS:
        base = os.path.join(root, conversation_id)
        if not os.path.isdir(base):
            continue
        for candidate in (
            os.path.join(base, ".system_generated", "logs", "transcript_full.jsonl"),
            os.path.join(base, ".system_generated", "logs", "transcript.jsonl"),
        ):
            if os.path.exists(candidate):
                return candidate, ""
        return "", f"spawned {label} {conversation_id[:8]} has no transcript file"
    return "", f"no transcript directory for spawned {label} {conversation_id[:8]}"


def read_subagent_verdict(conversation_id: str) -> Tuple[Optional[str], str]:
    path, err = _resolve_subagent_transcript(conversation_id, "critic")
    if not path:
        return None, err

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
                    content = _entry_model_text(entry)
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
            f"critic {conversation_id[:8]} transcript shows no real audit activity "
            f"({tool_steps} tool steps, {model_steps} model steps)"
        )
    if rejected:
        return "REJECTED", f"critic {conversation_id[:8]} returned CRITIC_VERDICT: REJECTED"
    if approved:
        return "APPROVED", f"critic {conversation_id[:8]} returned CRITIC_VERDICT: APPROVED"
    return None, f"critic {conversation_id[:8]} produced no verdict"


def detect_goldfish_spin(prompt: str) -> Optional[str]:
    if not prompt:
        return None
    for pattern in GOLDFISH_SPIN_PATTERNS:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def read_goldfish_dossier(conversation_id: str) -> Tuple[bool, str]:
    path, err = _resolve_subagent_transcript(conversation_id, "goldfish")
    if not path:
        return False, err

    model_steps = 0
    tool_calls_count = 0
    prose_chunks: List[str] = []
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
                    prose_chunks.append(_entry_model_text(entry))
                tcalls = entry.get("tool_calls") or []
                if isinstance(tcalls, list):
                    tool_calls_count += len([c for c in tcalls if isinstance(c, dict)])
    except Exception as exc:
        return False, f"goldfish transcript unreadable: {exc!r}"

    if tool_calls_count < 2 or model_steps < 1:
        return False, (
            f"goldfish {conversation_id[:8]} transcript shows no real audit activity "
            f"({tool_calls_count} tool calls, {model_steps} model steps)"
        )
    full_prose = "\n".join(prose_chunks)
    if REJECTED_VERDICT.search(full_prose) or APPROVED_VERDICT.search(full_prose):
        return False, (
            f"goldfish {conversation_id[:8]} violated role separation by emitting CRITIC_VERDICT "
            "(only black-hat-judge has verdict authority)"
        )
    if "FORENSIC_EVIDENCE_DOSSIER" not in full_prose:
        return False, f"goldfish {conversation_id[:8]} did not emit FORENSIC_EVIDENCE_DOSSIER"
    return True, f"goldfish {conversation_id[:8]} emitted FORENSIC_EVIDENCE_DOSSIER ({tool_calls_count} tool calls)"


def read_judge_verdict(judge_cid: str, goldfish_cid: str) -> Tuple[Optional[str], str]:
    path, err = _resolve_subagent_transcript(judge_cid, "judge")
    if not path:
        return None, err

    model_steps = 0
    tool_calls_count = 0
    first_tool_call: Optional[Tuple[str, Dict[str, Any]]] = None
    forbidden_tool: Optional[str] = None
    approved = False
    rejected = False
    mitm_detected = False

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
                    content = _entry_model_text(entry)
                    if re.search(r"MITM_LAUNDERING\s*:\s*\**\s*`?DETECTED", content, re.IGNORECASE):
                        mitm_detected = True
                    if REJECTED_VERDICT.search(content):
                        rejected = True
                    elif APPROVED_VERDICT.search(content):
                        approved = True
                for call in entry.get("tool_calls") or []:
                    if not isinstance(call, dict):
                        continue
                    tool_calls_count += 1
                    cname = str(call.get("name") or "")
                    cargs = _decode_args(call.get("args"))
                    if first_tool_call is None:
                        first_tool_call = (cname, cargs)
                    if cname == "run_command" or cname in MUTATING_TOOLS:
                        forbidden_tool = cname
    except Exception as exc:
        return None, f"judge transcript unreadable: {exc!r}"

    if tool_calls_count < 1 or model_steps < 1 or first_tool_call is None:
        return None, (
            f"judge {judge_cid[:8]} transcript shows no real audit activity "
            f"({tool_calls_count} tool calls, {model_steps} model steps)"
        )
    if forbidden_tool:
        return None, (
            f"judge {judge_cid[:8]} violated air-gap by calling {forbidden_tool} "
            "(judge must be zero-shell and read-only)"
        )

    first_name, first_args = first_tool_call
    first_path = str(
        first_args.get("AbsolutePath")
        or first_args.get("path")
        or first_args.get("TargetFile")
        or ""
    )
    valid_link = (
        first_name == "view_file"
        and goldfish_cid.lower() in first_path.lower()
        and (
            first_path.endswith("transcript.jsonl")
            or first_path.endswith("transcript_full.jsonl")
        )
    )
    if not valid_link:
        return None, (
            f"judge {judge_cid[:8]} first tool call ({first_name} -> {os.path.basename(first_path) or '<none>'}) "
            f"did not read spawned goldfish {goldfish_cid[:8]} transcript"
        )

    if rejected:
        return "REJECTED", f"judge {judge_cid[:8]} returned CRITIC_VERDICT: REJECTED"
    if mitm_detected:
        return (
            "REJECTED",
            f"judge {judge_cid[:8]} detected MITM_LAUNDERING between primary agent summary and goldfish {goldfish_cid[:8]} transcript",
        )
    if approved:
        return (
            "APPROVED",
            f"2-stage goldfish ({goldfish_cid[:8]}) -> judge ({judge_cid[:8]}) returned CRITIC_VERDICT: APPROVED",
        )
    return None, f"judge {judge_cid[:8]} produced no verdict"


def _extract_subagent_spawns(
    turn: List[Dict[str, Any]], target_typename: str
) -> List[Tuple[int, str, Optional[str], bool]]:
    target = target_typename.strip().lower()
    spawns: List[Tuple[int, str, Optional[str], bool]] = []
    for idx, entry in enumerate(turn):
        matched_prompts: List[Tuple[int, str]] = []
        for call in entry.get("tool_calls") or []:
            if not isinstance(call, dict) or call.get("name") != "invoke_subagent":
                continue
            call_args = _decode_args(call.get("args"))
            sub_list = call_args.get("Subagents")
            if isinstance(sub_list, str):
                try:
                    sub_list = json.loads(sub_list)
                except Exception:
                    sub_list = None
            if isinstance(sub_list, list) and sub_list:
                for sub_idx, s_item in enumerate(sub_list):
                    if isinstance(s_item, dict) and isinstance(s_item.get("TypeName"), str):
                        if s_item["TypeName"].strip().lower() == target:
                            matched_prompts.append(
                                (sub_idx, str(s_item.get("Prompt") or call_args.get("Prompt") or ""))
                            )
            elif isinstance(call_args.get("TypeName"), str):
                if call_args["TypeName"].strip().lower() == target:
                    matched_prompts.append((0, str(call_args.get("Prompt") or "")))
        if not matched_prompts:
            continue
        extracted_cids: List[str] = []
        for result in turn[idx + 1 :]:
            if result.get("type") in MODEL_PROSE_TYPES:
                break
            content = str(result.get("content") or "")
            if "conversationid" in content.lower():
                found = [cid.lower() for cid in extract_conversation_ids(content)]
                if found:
                    extracted_cids.extend(found)
                    break
        for pos, (sub_idx, prompt_text) in enumerate(matched_prompts):
            cid = None
            if sub_idx < len(extracted_cids):
                cid = extracted_cids[sub_idx]
            elif pos < len(extracted_cids):
                cid = extracted_cids[pos]
            is_handcuffed = bool(HANDCUFF_PROMPT_RE.search(prompt_text))
            spawns.append((idx, prompt_text, cid, is_handcuffed))
    return spawns


def find_goldfish_judge_proof(
    goldfish_spawns: List[Tuple[int, str, Optional[str], bool]],
    judge_spawns: List[Tuple[int, str, Optional[str], bool]],
) -> Tuple[bool, str]:
    if not goldfish_spawns:
        return (
            False,
            "black-hat-judge invoked without a preceding black-hat-goldfish investigation in this turn",
        )
    g_idx, g_prompt, g_cid, g_restricted = goldfish_spawns[-1]
    if g_restricted:
        return (
            False,
            "goldfish prompt restricted independent command execution ('view_file only' / 'do not run commands' is prohibited)",
        )
    spin_hit = detect_goldfish_spin(g_prompt)
    if spin_hit:
        return (
            False,
            f"goldfish prompt contains prohibited spin/excuse framing ({spin_hit!r}); pass de-contextualized claims, paths, and commands only",
        )
    if not g_cid:
        return False, "black-hat-goldfish invoked but no spawn result with a conversation id"

    gf_ok, gf_detail = read_goldfish_dossier(g_cid)
    if not gf_ok:
        return False, gf_detail

    if not judge_spawns:
        return (
            False,
            f"Stage-1 black-hat-goldfish ({g_cid[:8]}) completed FORENSIC_EVIDENCE_DOSSIER, "
            "but Stage-2 black-hat-judge has not been invoked yet; invoke black-hat-judge with goldfish transcript path",
        )

    j_idx, _j_prompt, j_cid, _j_restricted = judge_spawns[-1]
    if j_idx <= g_idx:
        if len(goldfish_spawns) > 1 and goldfish_spawns[0][0] < j_idx:
            return (
                False,
                f"Stage-1 black-hat-goldfish ({g_cid[:8]}) completed FORENSIC_EVIDENCE_DOSSIER, "
                "but Stage-2 black-hat-judge has not been invoked for this round yet; invoke black-hat-judge with goldfish transcript path",
            )
        return (
            False,
            f"black-hat-judge (step {j_idx}) must be invoked in a strictly later step after black-hat-goldfish (step {g_idx}) completes",
        )
    if not j_cid:
        return False, "black-hat-judge invoked but no spawn result with a conversation id"
    if j_cid == g_cid:
        return False, "black-hat-judge conversation id cannot equal black-hat-goldfish conversation id"

    verdict, j_detail = read_judge_verdict(j_cid, g_cid)
    if verdict == "APPROVED":
        return True, j_detail
    return False, j_detail


def find_structural_proof(turn: List[Dict[str, Any]]) -> Tuple[bool, str]:
    goldfish_spawns = _extract_subagent_spawns(turn, GOLDFISH_AGENT_NAME)
    judge_spawns = _extract_subagent_spawns(turn, JUDGE_AGENT_NAME)
    if goldfish_spawns or judge_spawns:
        return find_goldfish_judge_proof(goldfish_spawns, judge_spawns)

    if os.environ.get("BH_GATE_STRICT_TWO_STAGE") == "1":
        return False, "no 2-stage black-hat-goldfish -> black-hat-judge verification executed in this turn"

    critic_spawns = _extract_subagent_spawns(turn, CRITIC_AGENT_NAME)
    if not critic_spawns:
        return False, "no independent verification executed in this turn"

    spawn_ids = [cid for _, _, cid, restricted in critic_spawns if cid and not restricted]
    restricted_prompt_detected = any(restricted for _, _, _, restricted in critic_spawns)
    if not spawn_ids and restricted_prompt_detected:
        return (
            False,
            "critic prompt restricted independent command execution ('view_file only' / 'do not run commands' is prohibited)",
        )
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


def extract_pre_critic_response(turn: List[Dict[str, Any]]) -> str:
    last_audit_idx = -1
    for idx, entry in enumerate(turn):
        for call in entry.get("tool_calls") or []:
            if isinstance(call, dict) and call.get("name") == "invoke_subagent":
                tnames = critic_typenames(call.get("args") or {})
                if GOLDFISH_AGENT_NAME in tnames:
                    last_audit_idx = idx
                elif last_audit_idx < 0 and any(
                    t in tnames for t in (CRITIC_AGENT_NAME, JUDGE_AGENT_NAME)
                ):
                    last_audit_idx = idx
    search_slice = turn[:last_audit_idx] if last_audit_idx > 0 else turn[:-1]
    candidates: List[str] = []
    for entry in search_slice:
        if entry.get("type") not in MODEL_PROSE_TYPES:
            continue
        txt = str(entry.get("content") or "").strip()
        if not txt:
            continue
        if len(txt) < 220 and re.search(
            r"black[- ]hat[- ](?:critic|goldfish|judge)|FORENSIC_EVIDENCE_DOSSIER|verification pass|waiting for",
            txt,
            re.I,
        ):
            continue
        candidates.append(txt)
    if not candidates:
        return ""
    return max(candidates, key=len)


def is_bare_verdict_stub(final_text: str, pre_critic_text: str) -> bool:
    if len(pre_critic_text) < 240:
        return False
    clean_final = final_text.strip()
    if len(clean_final) < 200:
        return True
    has_structured_summary = bool(
        re.search(r"(^\s*[-*•]\s+|^\s*\d+\.\s+|\|.+\|)", clean_final, re.MULTILINE)
    )
    if not has_structured_summary and len(clean_final) < 350:
        return True
    return False


def bottom_summary_rejection_text(pre_critic_text: str, proof_detail: str) -> str:
    excerpt = pre_critic_text[:1800] + ("..." if len(pre_critic_text) > 1800 else "")
    return (
        "BLACK-HAT POST-CRITIC SUMMARY GATE: Your final message at the bottom of the turn "
        "is a short stub, forcing the user to scroll up past subagent cards to see the actual response.\n\n"
        f"Critic status: {proof_detail} (already APPROVED — do NOT re-spawn black-hat-goldfish/judge or black-hat-critic).\n\n"
        "Emit your final closing message now using the mandatory **Compact 2-Part Bottom Summary** format:\n"
        "  1. **Summary of Approved Response & Deliverables**: Concise bullet/table summary of the "
        "previous response, key findings, modified files/links, and metrics.\n"
        "  2. **1-Line Black-Hat Critic Verdict Badge**: `CRITIC_VERDICT: APPROVED | GCS = 1.000 | <N/N Checks Passed>`\n\n"
        "--- EXTRACTED PRE-CRITIC RESPONSE FROM TRANSCRIPT ---\n"
        f"{excerpt}\n"
        "-----------------------------------------------------"
    )


def rejection_text(
    mutations: List[str],
    claim: Optional[str],
    proof_detail: str,
    pre_critic_text: str = "",
) -> str:
    listed = "\n".join(f"   - {m}" for m in mutations[:8]) or "   - (none)"
    claim_line = f"Completion claim detected: \"{claim}\"\n" if claim else ""
    pre_block = ""
    if len(pre_critic_text) >= 180:
        excerpt = pre_critic_text[:1500] + ("..." if len(pre_critic_text) > 1500 else "")
        pre_block = (
            "\n\n--- EXTRACTED PRE-CRITIC RESPONSE TO SUMMARIZE AT BOTTOM ---\n"
            f"{excerpt}\n"
            "------------------------------------------------------------"
        )
    brain_root = BRAIN_CANDIDATE_ROOTS[0]
    return (
        "BLACK-HAT CRITIC GATE (v4.3 Goldfish -> Judge): independent verification missing.\n\n"
        f"{claim_line}"
        f"State mutated in this turn:\n{listed}\n\n"
        f"Gate status: {proof_detail}.\n\n"
        "Clear this gate by executing the **2-Stage Goldfish -> Judge Verification Protocol** "
        f"(or single-stage `{CRITIC_AGENT_NAME}` fallback):\n"
        f"  1. **Stage 1 (Stateless Goldfish Investigator)**: Call `invoke_subagent(TypeName=\"{GOLDFISH_AGENT_NAME}\")` "
        "with a CLAIMS-ONLY prompt containing ONLY itemized factual claims, target deliverable paths/IDs, and "
        "verification commands. Exclude all session narrative, excuses, and caveats, and never restrict command execution.\n"
        f"  2. **Stage 2 (Isolated Judge)**: After `{GOLDFISH_AGENT_NAME}` completes, call "
        f"`invoke_subagent(TypeName=\"{JUDGE_AGENT_NAME}\")` with the goldfish `conversationId`, the exact goldfish "
        f"transcript path (`{brain_root}/<goldfish_cid>/.system_generated/logs/transcript.jsonl`), the itemized claims, "
        "and deliverable paths. The judge must read the goldfish transcript as its first tool call and end with "
        "`CRITIC_VERDICT: APPROVED` or `CRITIC_VERDICT: REJECTED`.\n"
        "  3. **Stage 3 (Compact 2-Part Bottom Summary)**: Once APPROVED, your final closing message MUST include "
        "`### Summary of Approved Response & Deliverables` followed by `CRITIC_VERDICT: APPROVED | GCS = 1.000 | <N/N Checks Passed>`."
        f"{pre_block}"
    )


def run_attached_black_hat_verification(
    turn: List[Dict[str, Any]], artifact_dir: str
) -> Tuple[bool, List[str]]:
    failures: List[str] = []
    seen_targets = set()
    for name, args in iter_tool_calls(turn):
        if not isinstance(args, dict) or name not in FILE_MUTATING_TOOLS:
            continue
        raw_target = ""
        for key in TARGET_KEYS:
            if isinstance(args.get(key), str) and args.get(key):
                raw_target = args[key]
                break
        if not raw_target or is_exempt_target(raw_target, artifact_dir):
            continue
        normalized = _normalize(raw_target)
        if not normalized or normalized in seen_targets:
            continue
        seen_targets.add(normalized)

        parent_dir = os.path.dirname(normalized)
        if not parent_dir or not os.path.isdir(parent_dir):
            continue

        bname = os.path.basename(normalized)
        if not os.path.exists(normalized):
            failures.append(f"attached-check: mutated file missing on disk ({bname})")
            continue
        if os.path.isfile(normalized) and os.path.getsize(normalized) == 0:
            failures.append(f"attached-check: mutated file is empty 0 bytes ({bname})")
            continue

        if normalized.endswith(".py") and os.path.isfile(normalized):
            try:
                with open(normalized, "r", encoding="utf-8") as fh:
                    src = fh.read()
                tree = ast.parse(src, filename=normalized)
                py_compile.compile(normalized, doraise=True)
                if bname.startswith("test_") or bname.endswith("_test.py"):
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                            for sub in ast.walk(node):
                                if isinstance(sub, ast.Assert):
                                    if isinstance(sub.test, ast.Constant) and sub.test.value is True:
                                        failures.append(
                                            f"attached-check: AST test facade ('assert True') in {bname}:{node.name}"
                                        )
            except SyntaxError as exc:
                failures.append(f"attached-check: Python SyntaxError in {bname}:{exc.lineno}: {exc.msg}")
            except py_compile.PyCompileError as exc:
                failures.append(f"attached-check: py_compile failed for {bname}: {exc.msg}")
            except Exception as exc:
                failures.append(f"attached-check: Python verification error in {bname}: {exc!r}")

        elif normalized.endswith(".json") and os.path.isfile(normalized):
            try:
                with open(normalized, "r", encoding="utf-8") as fh:
                    json.load(fh)
            except Exception as exc:
                failures.append(f"attached-check: Invalid JSON in {bname}: {exc}")

    return len(failures) == 0, failures


def last_critic_step_index(turn: List[Dict[str, Any]]) -> int:
    last_idx = -1
    for idx, entry in enumerate(turn):
        for call in entry.get("tool_calls") or []:
            if isinstance(call, dict) and call.get("name") == "invoke_subagent":
                tnames = critic_typenames(call.get("args") or {})
                if any(t in tnames for t in (CRITIC_AGENT_NAME, JUDGE_AGENT_NAME)):
                    last_idx = idx
    return last_idx


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
    if "<hydrated_context>" in seed or "MAX_DEPTH=1" in seed:
        return allow("leaf subagent conversation (<hydrated_context> / MAX_DEPTH=1) is exempt")
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
    if is_simple_question_turn(steps, mutations, final_text):
        return allow("simple question / read-only turn with no deliverable")

    claim = detect_completion_claim(final_text)
    if not mutations and not claim:
        return allow("read-only turn with no completion claim")

    pre_critic_text = extract_pre_critic_response(turn)
    attached_ok, attached_failures = run_attached_black_hat_verification(turn, artifact_dir)
    if not attached_ok:
        attached_detail = "in-process attached verification failed: " + "; ".join(attached_failures)
        return {
            "decision": "continue",
            "reason": rejection_text(mutations, claim, attached_detail, pre_critic_text),
            "audit": f"blocked: {attached_detail}",
            "mutations": len(mutations),
            "claim": claim,
        }

    proof_found, proof_detail = find_structural_proof(turn)
    if proof_found:
        critic_idx = last_critic_step_index(turn)
        post_critic_mutations = (
            detect_mutations(turn[critic_idx + 1 :], artifact_dir) if critic_idx >= 0 else []
        )
        if post_critic_mutations:
            post_detail = (
                f"state mutated after critic/judge ran ({', '.join(post_critic_mutations[:3])}); "
                "re-run verification as the final step after all mutations"
            )
            return {
                "decision": "continue",
                "reason": rejection_text(mutations, claim, post_detail, pre_critic_text),
                "audit": f"blocked: {post_detail}",
                "mutations": len(mutations),
                "claim": claim,
            }
        if is_bare_verdict_stub(final_text, pre_critic_text):
            return {
                "decision": "continue",
                "reason": bottom_summary_rejection_text(pre_critic_text, proof_detail),
                "audit": "blocked: post-critic final_text is a bare stub missing bottom summary",
                "mutations": len(mutations),
                "claim": claim,
            }
        return allow(
            f"verified: {proof_detail} + in-process attached checks passed",
            mutations=len(mutations),
            claim=claim,
        )

    return {
        "decision": "continue",
        "reason": rejection_text(mutations, claim, proof_detail, pre_critic_text),
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
