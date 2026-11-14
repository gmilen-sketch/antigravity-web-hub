#!/usr/bin/env python3
"""Black-Hat Critic Stop Gate (v4.18 - Adaptive Multi-Goldfish Wave -> Holistic Judge, Clean-Room Edition).

Antigravity & Multi-Harness `Stop` lifecycle hook. Forces the agent to run an independent
adversarial verification pass before ending a turn in which it mutated state or declared completion.

Design invariants (v4.18):
  1. TURN SCOPE      - evidence is read only from the current turn (after the last USER_INPUT step).
  2. DEFAULT-DENY    - triggers on durable state mutation or explicit deliverable/completion claims.
  3. STRUCTURAL PROOF- Primary route: 2-stage `black-hat-goldfish` (`K=1..3` `[SHARD:<id>]` wave, C1-C5)
                       followed by `black-hat-judge` (holistic adjudicator reading 100% shard transcripts, C6-C8).
                       Fallback route: single-stage `black-hat-critic` when neither goldfish nor judge was invoked.
  4. ATTACHED CHECKS - runs in-process AST/JSON/file-size/test-facade verification (`compile()`, zero `.pyc`).
  5. BOTTOM SUMMARY  - enforces Compact 2-Part Bottom Summary & restores held-back deliverable artifact cards.
  6. BOUNDED         - self-throttles on `executionNum` at MAX_FORCED_CONTINUATIONS.
  7. NON-RECURSIVE   - never gates critic/goldfish/judge/leaf subagents or verified isolated SWE sandboxes.
"""

import ast
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.dont_write_bytecode = True

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

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
    "research-assistant",
    "custom_subagent",
    "workspace-housekeeper",
    "workspace_housekeeper",
    "dreaming-improvement-reasoner",
    "dreaming_improvement_reasoner",
    "self",
}

HANDCUFF_PROMPT_RE = re.compile(
    r"\b(use\s+`?(?:view_file|read_file)`?\s+only|(?:view_file|read_file)\s+only|do\s+not\s+run\s+(?:any\s+)?(?:shell\s+)?commands(?:\s*$|\s*[.;,)])|skip\s+`?run_command`?|without\s+running\s+commands)\b",
    re.IGNORECASE,
)

SHARD_TAG_RE = re.compile(r"\[SHARD:([A-Za-z0-9_.\-]{1,40})\]", re.IGNORECASE)
URL_STRIP_RE = re.compile(r"https?://[^\s<>)\]`\"']+", re.IGNORECASE)

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
    "write_file",
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
    "notebook_edit",
    "edit_file",
    "create_file",
    "Write",
    "Edit",
    "MultiEdit",
}

MUTATING_TOOLS = FILE_MUTATING_TOOLS | {
    "generate_image",
}

TARGET_KEYS = ("Path", "TargetFile", "AbsolutePath", "NotebookPath", "path", "file_path", "ImageName")

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
    r"(?<![0-9<>-])>>?(?![=>&])\s*(?!/dev/null(?:\s|$|[;&|)])|&[12]\b|['\"]?(?:/tmp/|/dev/shm/))[^\s|&;)]+",
]

BENIGN_FD_REDIRECT_RE = re.compile(
    r"(?:\b[12]?\s*>\s*/dev/null\b|\b[12]>\s*&[12]\b|&>\s*/dev/null\b)"
)

INLINE_PYTHON_EXEMPT_CALL_RE = re.compile(
    r"""(?x)
    \bopen\s*\(\s*[fFrRuU]*['"](?:/tmp/|/dev/shm/|[^'"]*/scratch/)[^'"]*['"]\s*,\s*['"][wa+][A-Za-z0-9+]*['"][^)]*\)
    | \b(?:pathlib\.)?Path\s*\(\s*[fFrRuU]*['"](?:/tmp/|/dev/shm/|[^'"]*/scratch/)[^'"]*['"]\s*\)\s*\.\s*(?:write_text|write_bytes|unlink)\s*\(
    | \bos\.(?:remove|unlink)\s*\(\s*[fFrRuU]*['"](?:/tmp/|/dev/shm/|[^'"]*/scratch/)[^'"]*['"]\s*\)
    """
)

INLINE_PYTHON_WRITE_RE = re.compile(
    r"""(?x)
    \bopen\s*\([^)]*,\s*['"][wa+][A-Za-z0-9+]*['"]
    | \.(?:write_text|write_bytes)\s*\(
    | \bshutil\.(?:copy|copy2|copytree|move|rmtree)\s*\(
    | \bos\.(?:remove|unlink|rename|replace)\s*\(
    """
)

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
    os.path.expanduser(os.environ.get("ANTIGRAVITY_BRAIN_DIR") or "~/.gemini/antigravity/brain"),
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


def _strip_heredoc_and_quotes_fallback(cmd: str) -> str:
    if not cmd:
        return ""
    lines = cmd.splitlines()
    out_lines: List[str] = []
    end_tag: Optional[str] = None
    for ln in lines:
        if end_tag is not None:
            if ln.strip() == end_tag:
                end_tag = None
            continue
        m = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", ln)
        out_lines.append(re.sub(r"<<-?\s*['\"]?[A-Za-z_][A-Za-z0-9_]*['\"]?.*$", "", ln))
        if m:
            end_tag = m.group(1)
    stripped = "\n".join(out_lines)
    stripped = re.sub(r"'[^']*'", "''", stripped)
    stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', stripped)
    return stripped


def _extract_inline_python_payloads(command: str) -> str:
    if not command:
        return ""
    extracted: List[str] = []
    norm_cmd = (
        command.replace("\\n", "\n").replace('\\"', '"')
        if ("\n" not in command and "\\n" in command)
        else command
    )
    for m in re.finditer(
        r"(?ms)\bpython3?[^\n;|]*<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n(.*?)(?:\n\1\b|\Z)",
        norm_cmd,
    ):
        extracted.append(m.group(2) or "")
    for m in re.finditer(
        r"(?s)\bpython3?\s+(?:-[A-Za-z0-9]+\s+)*-c\s+(?:'([^']*)'|\"((?:\\.|[^\"\\])*)\")",
        norm_cmd,
    ):
        extracted.append(m.group(1) if m.group(1) is not None else (m.group(2) or ""))
    return "\n".join(extracted)


def is_mutating_command(command: str) -> bool:
    if not command:
        return False
    try:
        try:
            from src.hooks.sentinel_dispatch import strip_heredoc_and_quoted_literals
        except ImportError:
            from sentinel_dispatch import strip_heredoc_and_quoted_literals  # type: ignore
    except Exception:
        strip_heredoc_and_quoted_literals = _strip_heredoc_and_quotes_fallback

    norm_cmd = (
        command.replace("\\n", "\n").replace('\\"', '"')
        if ("\n" not in command and "\\n" in command)
        else command
    )
    shell_surface = BENIGN_FD_REDIRECT_RE.sub(" ", strip_heredoc_and_quoted_literals(norm_cmd))
    for pattern in MUTATING_COMMAND_PATTERNS:
        if re.search(pattern, shell_surface, re.IGNORECASE):
            return True

    inline_py = _extract_inline_python_payloads(norm_cmd)
    if inline_py:
        cleaned_py = INLINE_PYTHON_EXEMPT_CALL_RE.sub("", inline_py)
        if INLINE_PYTHON_WRITE_RE.search(cleaned_py):
            return True
    return False


MUTATING_MCP_PREFIXES = (
    "create_",
    "delete_",
    "update_",
    "write_",
    "mutate_",
    "insert_",
    "remove_",
    "patch_",
    "drop_",
    "upsert_",
    "put_",
    "post_",
    "send_",
    "apply_",
    "assign_",
    "edit_",
    "add_",
    "cancel_",
    "set_",
)


def is_mutating_mcp(tool_name: str, args: Dict[str, Any]) -> bool:
    raw = (tool_name or "").lower()
    if raw == "call_mcp_tool":
        name = str(args.get("ToolName") or "").lower()
        candidates = [name] if name else []
    elif raw.startswith("mcp_"):
        rest = raw[4:]
        if "_" not in rest:
            return True
        candidates = [
            rest[idx + 1 :]
            for idx, ch in enumerate(rest)
            if ch == "_" and rest[idx + 1 :]
        ]
    else:
        return False
    if not candidates:
        return True
    if any(marker in candidates[0] for marker in READONLY_MCP_MARKERS):
        return False
    if any(cand.startswith(MUTATING_MCP_PREFIXES) for cand in candidates):
        return True
    if any(cand == "execute_sql" for cand in candidates):
        return True
    return not any(cand.startswith(READONLY_MCP_PREFIXES) for cand in candidates)


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
        if name in ("run_command", "Bash", "bash"):
            command = str(args.get("CommandLine") or args.get("command") or "")
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
    cleaned = URL_STRIP_RE.sub(" ", prompt)
    for pattern in GOLDFISH_SPIN_PATTERNS:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def detect_goldfish_transcript_mutations(entries: List[Dict[str, Any]], goldfish_cid: str) -> Optional[str]:
    """GOLDFISH-RO-1 (`C3b`): Scans Stage-1 goldfish transcript for prohibited disk mutations."""
    try:
        from sentinel_dispatch import enforce_goldfish_readonly_command
    except Exception:
        enforce_goldfish_readonly_command = None

    for entry in entries:
        for call in entry.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            cname = str(call.get("name") or "")
            cargs = _decode_args(call.get("args"))
            if cname in MUTATING_TOOLS:
                return f"goldfish {goldfish_cid[:8]} called prohibited mutating tool '{cname}' (GOLDFISH-RO-1 C3b)"
            if cname == "run_command" and enforce_goldfish_readonly_command is not None:
                res = enforce_goldfish_readonly_command(
                    "run_command",
                    cargs,
                    agent_name=GOLDFISH_AGENT_NAME,
                    conversation_id=goldfish_cid,
                )
                if res is not None and res.get("decision") == "deny":
                    return f"goldfish {goldfish_cid[:8]} executed prohibited mutating shell command ({res.get('reason', '')})"
    return None


def _parse_discrepancy_count(text: str) -> Optional[int]:
    matches = re.findall(r"DISCREPANCY_COUNT\s*:\s*\**\s*`?(\d+)`?", text or "", re.IGNORECASE)
    if not matches:
        return None
    try:
        return int(matches[-1])
    except ValueError:
        return None


def read_goldfish_dossier(conversation_id: str) -> Tuple[bool, str]:
    path, err = _resolve_subagent_transcript(conversation_id, "goldfish")
    if not path:
        return False, err

    model_steps = 0
    tool_calls_count = 0
    prose_chunks: List[str] = []
    parsed_entries: List[Dict[str, Any]] = []
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
                parsed_entries.append(entry)
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

    mut_hit = detect_goldfish_transcript_mutations(parsed_entries, conversation_id)
    if mut_hit:
        return False, mut_hit

    full_prose = "\n".join(prose_chunks)
    if REJECTED_VERDICT.search(full_prose) or APPROVED_VERDICT.search(full_prose):
        return False, (
            f"goldfish {conversation_id[:8]} violated role separation by emitting CRITIC_VERDICT "
            "(only black-hat-judge has verdict authority)"
        )
    if "FORENSIC_EVIDENCE_DOSSIER" not in full_prose:
        return False, f"goldfish {conversation_id[:8]} did not emit FORENSIC_EVIDENCE_DOSSIER"
    disc_count = _parse_discrepancy_count(full_prose)
    if disc_count is not None and disc_count > 0:
        return False, (
            f"goldfish {conversation_id[:8]} reported DISCREPANCY_COUNT: {disc_count} (> 0); "
            "remediate all discrepancies and re-verify affected shard(s) before invoking black-hat-judge"
        )
    return True, f"goldfish {conversation_id[:8]} emitted FORENSIC_EVIDENCE_DOSSIER (DISCREPANCY_COUNT=0, {tool_calls_count} tool calls)"


def read_judge_verdict(judge_cid: str, goldfish_cids: Any) -> Tuple[Optional[str], str]:
    """v4.18 Holistic Judge Validator (`C6-Multi` + `C6-Holistic`): accepts single `str` or `List[str]` of active shard CIDs."""
    wave_cids: List[str] = (
        [goldfish_cids.lower()]
        if isinstance(goldfish_cids, str)
        else [str(c).lower() for c in (goldfish_cids or []) if c]
    )
    if not wave_cids:
        return None, f"judge {judge_cid[:8]} invoked with empty goldfish wave"

    path, err = _resolve_subagent_transcript(judge_cid, "judge")
    if not path:
        return None, err

    model_steps = 0
    tool_calls_count = 0
    read_paths: List[Tuple[str, str]] = []
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
                    if cname in ("read_file", "view_file", "Read"):
                        rp = str(
                            cargs.get("Path")
                            or cargs.get("AbsolutePath")
                            or cargs.get("path")
                            or cargs.get("TargetFile")
                            or cargs.get("file_path")
                            or ""
                        )
                        read_paths.append((cname, rp))
                    elif cname in ("run_command", "Bash", "bash", "invoke_subagent", "define_subagent") or cname in MUTATING_TOOLS:
                        forbidden_tool = cname
    except Exception as exc:
        return None, f"judge transcript unreadable: {exc!r}"

    if tool_calls_count < 1 or model_steps < 1 or not read_paths:
        return None, (
            f"judge {judge_cid[:8]} transcript shows no real audit activity "
            f"({tool_calls_count} tool calls, {model_steps} model steps)"
        )
    if forbidden_tool:
        return None, (
            f"judge {judge_cid[:8]} violated air-gap by calling {forbidden_tool} "
            "(judge must be zero-shell and read-only)"
        )

    def _is_gf_transcript(p: str, target_cid: str) -> bool:
        pl = p.lower()
        return target_cid in pl and (pl.endswith("transcript.jsonl") or pl.endswith("transcript_full.jsonl"))

    first_name, first_path = read_paths[0]
    if not any(_is_gf_transcript(first_path, gcid) for gcid in wave_cids):
        return None, (
            f"judge {judge_cid[:8]} first tool call ({first_name} -> {os.path.basename(first_path) or '<none>'}) "
            f"did not read an active goldfish shard transcript ({', '.join(c[:8] for c in wave_cids)})"
        )

    missing_cids = [gcid for gcid in wave_cids if not any(_is_gf_transcript(rp, gcid) for _, rp in read_paths)]
    if missing_cids:
        return None, (
            f"judge {judge_cid[:8]} failed C6-Multi: did not read active goldfish shard transcript(s) "
            f"{', '.join(c[:8] for c in missing_cids)}"
        )

    if len(wave_cids) >= 2:
        deliverable_reads = [
            rp for _, rp in read_paths
            if rp and not any(_is_gf_transcript(rp, gcid) for gcid in wave_cids)
            and not rp.lower().endswith(("transcript.jsonl", "transcript_full.jsonl"))
        ]
        if not deliverable_reads:
            return None, (
                f"judge {judge_cid[:8]} failed C6-Holistic: K={len(wave_cids)} goldfish shards active, "
                "so judge must also spot-check >= 1 deliverable via read_file for cross-shard seam validation"
            )

    if rejected:
        return "REJECTED", f"judge {judge_cid[:8]} returned CRITIC_VERDICT: REJECTED"
    if mitm_detected:
        return (
            "REJECTED",
            f"judge {judge_cid[:8]} detected MITM_LAUNDERING between primary agent summary and goldfish wave ({', '.join(c[:8] for c in wave_cids)})",
        )
    if approved:
        wave_lbl = ",".join(c[:8] for c in wave_cids)
        return (
            "APPROVED",
            f"2-stage goldfish ({wave_lbl}; K={len(wave_cids)}) -> judge ({judge_cid[:8]}) returned CRITIC_VERDICT: APPROVED",
        )
    return None, f"judge {judge_cid[:8]} produced no verdict"


def _extract_shard_id(role_text: str, prompt_text: str) -> Optional[str]:
    m = SHARD_TAG_RE.search(f"{role_text or ''} {prompt_text or ''}")
    return m.group(1).lower() if m else None


def _extract_subagent_spawns(
    turn: List[Dict[str, Any]], target_typename: str
) -> List[Tuple[int, str, Optional[str], bool, Optional[str]]]:
    """v4.18 parallel-safe subagent spawn extractor (`flat_sub_idx` across co-spawned tool_calls + `[SHARD:<id>]`)."""
    target = target_typename.strip().lower()
    spawns: List[Tuple[int, str, Optional[str], bool, Optional[str]]] = []
    for idx, entry in enumerate(turn):
        matched_prompts: List[Tuple[int, str, Optional[str]]] = []
        flat_sub_idx = 0
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
                for s_item in sub_list:
                    if isinstance(s_item, dict):
                        tname = str(s_item.get("TypeName") or "").strip().lower()
                        if tname == target:
                            ptxt = str(s_item.get("Prompt") or call_args.get("Prompt") or "")
                            rtxt = str(s_item.get("Role") or call_args.get("Role") or "")
                            matched_prompts.append((flat_sub_idx, ptxt, _extract_shard_id(rtxt, ptxt)))
                    flat_sub_idx += 1
            elif isinstance(call_args.get("TypeName"), str):
                tname = call_args["TypeName"].strip().lower()
                if tname == target:
                    ptxt = str(call_args.get("Prompt") or "")
                    rtxt = str(call_args.get("Role") or "")
                    matched_prompts.append((flat_sub_idx, ptxt, _extract_shard_id(rtxt, ptxt)))
                flat_sub_idx += 1
        if not matched_prompts:
            continue
        extracted_cids: List[str] = []
        for result in turn[idx + 1 :]:
            if result.get("type") in MODEL_PROSE_TYPES or result.get("type") == "USER_INPUT":
                break
            content = str(result.get("content") or "")
            if "conversationid" in content.lower():
                found = [cid.lower() for cid in extract_conversation_ids(content)]
                for fcid in found:
                    if fcid not in extracted_cids:
                        extracted_cids.append(fcid)
                if len(extracted_cids) >= flat_sub_idx:
                    break
        for pos, (sub_idx, prompt_text, shard_id) in enumerate(matched_prompts):
            cid = None
            if sub_idx < len(extracted_cids):
                cid = extracted_cids[sub_idx]
            elif pos < len(extracted_cids) and flat_sub_idx == len(matched_prompts):
                cid = extracted_cids[pos]
            is_handcuffed = bool(HANDCUFF_PROMPT_RE.search(prompt_text))
            spawns.append((idx, prompt_text, cid, is_handcuffed, shard_id))
    return spawns


def resolve_active_goldfish_wave(
    goldfish_spawns: List[Tuple[int, str, Optional[str], bool, Optional[str]]],
    judge_spawns: List[Tuple[int, str, Optional[str], bool, Optional[str]]],
) -> List[Tuple[int, str, Optional[str], bool, Optional[str]]]:
    """Resolves the active `K=1..3` Goldfish wave after the most recent rejected/superseded Judge round."""
    if not goldfish_spawns:
        return []
    last_gf_step = goldfish_spawns[-1][0]
    prior_judges = [j[0] for j in judge_spawns if j[2] and j[0] < last_gf_step]
    wave_floor = (max(prior_judges) + 1) if prior_judges else 0
    post_floor = [g for g in goldfish_spawns if g[0] >= wave_floor]
    if not post_floor:
        post_floor = [goldfish_spawns[-1]]

    has_any_shard_tag = any(g[4] is not None for g in post_floor)
    if has_any_shard_tag:
        latest_untagged_step = max((g[0] for g in post_floor if g[4] is None), default=-1)
        sharded_after = [g for g in post_floor if g[0] > latest_untagged_step]
        if not sharded_after:
            return [g for g in post_floor if g[0] == latest_untagged_step]
        by_shard: Dict[str, Tuple[int, str, Optional[str], bool, Optional[str]]] = {}
        untagged_same_step: List[Tuple[int, str, Optional[str], bool, Optional[str]]] = []
        for item in sharded_after:
            sid = item[4]
            if sid:
                by_shard[sid] = item
            else:
                untagged_same_step.append(item)
        return list(by_shard.values()) + untagged_same_step

    return [g for g in post_floor if g[0] == last_gf_step]


def _validate_active_goldfish_wave(
    active_wave: List[Tuple[int, str, Optional[str], bool, Optional[str]]],
    min_wave_idx: int,
) -> Tuple[bool, str, List[str]]:
    wave_cids: List[str] = []
    for g_idx, g_prompt, g_cid, g_restricted, g_shard in active_wave:
        shard_lbl = f" [SHARD:{g_shard}]" if g_shard else ""
        if g_restricted:
            return (
                False,
                f"goldfish{shard_lbl} prompt restricted independent command execution ('read_file only' / 'do not run commands' is prohibited)",
                [],
            )
        spin_hit = detect_goldfish_spin(g_prompt)
        if spin_hit:
            return (
                False,
                f"goldfish{shard_lbl} prompt contains prohibited spin/excuse framing ({spin_hit!r}); pass de-contextualized claims, paths, and commands only",
                [],
            )
        if not g_cid:
            return False, f"black-hat-goldfish{shard_lbl} invoked at step {g_idx} without a resolved conversationId", []
        gf_ok, gf_detail = read_goldfish_dossier(g_cid)
        if not gf_ok:
            return False, f"{gf_detail}{shard_lbl}", []
        if g_cid not in wave_cids:
            wave_cids.append(g_cid)
    return True, "", wave_cids


def _evaluate_critic_spawns(
    critic_spawns: List[Tuple[int, str, Optional[str], bool, Optional[str]]],
    min_step_after: int = -1,
) -> Tuple[bool, str, int]:
    scoped = [c for c in critic_spawns if c[0] > min_step_after]
    if not scoped:
        return False, "no independent verification executed in this turn", -1

    spawn_pairs = [(idx, cid) for idx, _, cid, restricted, _ in scoped if cid and not restricted]
    restricted_prompt_detected = any(restricted for _, _, _, restricted, _ in scoped)
    if not spawn_pairs and restricted_prompt_detected:
        return (
            False,
            "critic prompt restricted independent command execution ('read_file only' / 'do not run commands' is prohibited)",
            -1,
        )
    if not spawn_pairs:
        return False, "critic subagent invoked without a resolved conversation id", -1

    seen_cids: List[Tuple[int, str]] = []
    for s_idx, s_cid in spawn_pairs:
        if s_cid not in {c for _, c in seen_cids}:
            seen_cids.append((s_idx, s_cid))
    for s_idx, s_cid in reversed(seen_cids):
        verdict, detail = read_subagent_verdict(s_cid)
        if verdict == "APPROVED":
            return True, detail, s_idx
        if verdict == "REJECTED":
            return False, detail, s_idx
    _, last_detail = read_subagent_verdict(seen_cids[-1][1])
    return False, last_detail or "critic produced no verdict", seen_cids[-1][0]


def find_goldfish_judge_proof(
    goldfish_spawns: List[Tuple[int, str, Optional[str], bool, Optional[str]]],
    judge_spawns: List[Tuple[int, str, Optional[str], bool, Optional[str]]],
) -> Tuple[bool, str, int]:
    """v4.18 Multi-Goldfish Wave Barrier (`C2-Wave`, `C4b-Wave`, `C5b-Wave`, `C6-Multi`, `C6-Holistic`, `C10b`)."""
    if not goldfish_spawns:
        return (
            False,
            "black-hat-judge invoked without a preceding black-hat-goldfish investigation in this turn",
            -1,
        )

    active_wave = resolve_active_goldfish_wave(goldfish_spawns, judge_spawns)
    min_wave_idx = min(g[0] for g in active_wave)
    max_wave_idx = max(g[0] for g in active_wave)

    wave_ok, wave_err, wave_cids = _validate_active_goldfish_wave(active_wave, min_wave_idx)
    if not wave_ok:
        return False, wave_err, min_wave_idx

    if not judge_spawns:
        return (
            False,
            f"Stage-1 black-hat-goldfish wave ({','.join(c[:8] for c in wave_cids)}; K={len(wave_cids)}) completed FORENSIC_EVIDENCE_DOSSIER, "
            "but Stage-2 black-hat-judge has not been invoked yet; invoke black-hat-judge with all active goldfish transcript paths",
            min_wave_idx,
        )

    post_wave_judges = [j for j in judge_spawns if j[0] > max_wave_idx]
    resolved_post_wave_judges = [j for j in post_wave_judges if j[2]]
    selected_judge = resolved_post_wave_judges[-1] if resolved_post_wave_judges else judge_spawns[-1]

    j_idx, _j_prompt, j_cid, _j_restricted, _j_shard = selected_judge
    if j_idx <= max_wave_idx:
        if any(g[0] < j_idx for g in goldfish_spawns):
            return (
                False,
                f"Stage-1 black-hat-goldfish wave ({','.join(c[:8] for c in wave_cids)}) completed after earlier judge step {j_idx}; "
                "invoke Stage-2 black-hat-judge for the updated goldfish wave",
                min_wave_idx,
            )
        return (
            False,
            f"black-hat-judge (step {j_idx}) must be invoked in a strictly later step after all active black-hat-goldfish shards (step {max_wave_idx}) complete",
            min_wave_idx,
        )
    if not j_cid:
        return False, "black-hat-judge invoked without a resolved conversationId", min_wave_idx
    if j_cid in wave_cids:
        return False, "black-hat-judge conversation id cannot equal any black-hat-goldfish conversation id", min_wave_idx

    verdict, j_detail = read_judge_verdict(j_cid, wave_cids)
    if verdict == "APPROVED":
        return True, j_detail, min_wave_idx
    return False, j_detail, min_wave_idx


def find_structural_proof(turn: List[Dict[str, Any]]) -> Tuple[bool, str]:
    ok, detail, _ = find_structural_proof_with_index(turn)
    return ok, detail


def find_structural_proof_with_index(turn: List[Dict[str, Any]]) -> Tuple[bool, str, int]:
    goldfish_spawns = _extract_subagent_spawns(turn, GOLDFISH_AGENT_NAME)
    judge_spawns = _extract_subagent_spawns(turn, JUDGE_AGENT_NAME)
    strict_two_stage = os.environ.get("BH_GATE_STRICT_TWO_STAGE") == "1"

    if goldfish_spawns or judge_spawns:
        gj_ok, gj_detail, min_wave_idx = find_goldfish_judge_proof(goldfish_spawns, judge_spawns)
        if gj_ok or strict_two_stage:
            return gj_ok, gj_detail, min_wave_idx

        critic_spawns = _extract_subagent_spawns(turn, CRITIC_AGENT_NAME)
        if goldfish_spawns and critic_spawns:
            active_wave = resolve_active_goldfish_wave(goldfish_spawns, judge_spawns)
            w_min = min(g[0] for g in active_wave)
            w_max = max(g[0] for g in active_wave)
            wave_ok, _wave_err, wave_cids = _validate_active_goldfish_wave(active_wave, w_min)
            has_resolved_post_wave_judge = any(bool(j[2]) for j in judge_spawns if j[0] > w_max)
            if wave_ok and not has_resolved_post_wave_judge:
                c_ok, c_detail, _c_idx = _evaluate_critic_spawns(critic_spawns, min_step_after=w_max)
                if c_ok:
                    wave_lbl = ",".join(c[:8] for c in wave_cids)
                    return (
                        True,
                        f"Stage-1 goldfish ({wave_lbl}) + fallback {c_detail}",
                        w_min,
                    )
        elif not goldfish_spawns and critic_spawns and all(not j[2] for j in judge_spawns):
            max_aborted_j = max((j[0] for j in judge_spawns), default=-1)
            c_ok, c_detail, c_idx = _evaluate_critic_spawns(critic_spawns, min_step_after=max_aborted_j)
            if c_ok:
                return True, c_detail, c_idx

        return gj_ok, gj_detail, min_wave_idx

    if strict_two_stage:
        return False, "no 2-stage black-hat-goldfish -> black-hat-judge verification executed in this turn", -1

    critic_spawns = _extract_subagent_spawns(turn, CRITIC_AGENT_NAME)
    return _evaluate_critic_spawns(critic_spawns)


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
        "BLACK-HAT CRITIC GATE (v4.18 Adaptive Goldfish -> Holistic Judge): independent verification missing.\n\n"
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
        if os.path.islink(normalized):
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
                compile(src, normalized, "exec")
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


def detect_case_r_reactive_task_wakeup(turn: List[Dict[str, Any]], steps: List[Dict[str, Any]]) -> bool:
    """Case R Reactive `/task-` Wakeup Phase-2 Write Unlock."""
    for entry in reversed(steps[-6:] if len(steps) >= 6 else steps):
        content = str(entry.get("content") or "")
        if "/task-" in content or "background task" in content.lower() or "subagent completed" in content.lower():
            return True
    for entry in turn:
        content = str(entry.get("content") or "")
        if "/task-" in content:
            return True
    return False


def is_isolated_swe_sandbox_turn(payload: Dict[str, Any], seed_text: str) -> bool:
    """Short-circuits enterprise multi-subagent Stop gating when running inside an isolated SWE/TBench container."""
    if os.environ.get("ANTIGRAVITY_SWE_SANDBOX") == "1" or os.environ.get("TBENCH_SANDBOX") == "1":
        return True
    cwd = str(payload.get("cwd") or os.getcwd())
    if cwd.startswith("/testbed") or "/workspace/swe-bench" in cwd:
        return True
    if seed_text and ("/testbed" in seed_text or "terminal-bench" in seed_text.lower()):
        return True
    return False


def _restore_held_artifacts(artifact_dir: str) -> List[str]:
    if not artifact_dir:
        return []
    try:
        from black_hat_in_progress_ux_hook import restore_deliverable_artifact_cards

        return restore_deliverable_artifact_cards(artifact_dir)
    except Exception:
        return []


def _is_isolated_swe_benchmark_turn(payload: Dict[str, Any]) -> bool:
    if os.environ.get("AGW_EXECUTION_MODE", "").strip().upper() == "SWE_BENCHMARK_MODE":
        return True
    try:
        from kg_pre_invocation_hook import classify_execution_mode

        mode_res = classify_execution_mode(
            str(payload.get("prompt") or ""),
            cwd=str(payload.get("cwd") or ""),
        )
        return mode_res.get("mode") == "SWE_BENCHMARK_MODE"
    except Exception:
        return False


def evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
    reason_code = get_str(payload, "terminationReason", "termination_reason").upper()
    reason_code = reason_code.replace("EXECUTOR_TERMINATION_REASON_", "")
    agent_name = get_str(payload, "agentName", "agent_name").lower()
    execution_num = get_int(payload, "executionNum", "execution_num")
    transcript_path = get_str(payload, "transcriptPath", "transcript_path")
    artifact_dir = get_str(payload, "artifactDirectoryPath", "artifact_directory_path")
    fully_idle = payload.get("fullyIdle", payload.get("fully_idle", True))

    root_cid = get_str(payload, "rootConversationId", "root_conversation_id", "conversationId", "conversation_id", "session_id")

    def allow(why: str, restore_cards: bool = True, **extra: Any) -> Dict[str, Any]:
        restored: List[str] = []
        if restore_cards and fully_idle is not False and agent_name not in NON_GATED_AGENTS:
            restored = _restore_held_artifacts(artifact_dir)
        out = {"decision": "allow", "audit": why, "rootConversationId": root_cid}
        if restored:
            out["restoredArtifacts"] = restored
        out.update(extra)
        return out

    if reason_code in NON_GATED_TERMINATIONS:
        return allow(f"termination reason {reason_code} is not gated")

    if agent_name in NON_GATED_AGENTS:
        return allow(f"agent {agent_name} is exempt", restore_cards=False)

    if fully_idle is False:
        return allow("dependents still running", restore_cards=False)

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

    if is_isolated_swe_sandbox_turn(payload, seed):
        return allow("isolated SWE/TBench sandbox turn short-circuited")

    turn = slice_current_turn(steps)
    case_r_wakeup = detect_case_r_reactive_task_wakeup(turn, steps)

    if turn:
        attached_ok_early, attached_failures_early = run_attached_black_hat_verification(turn, artifact_dir)
        if not attached_ok_early:
            attached_detail_early = "in-process attached verification failed: " + "; ".join(attached_failures_early)
            return {
                "decision": "continue",
                "reason": rejection_text(detect_mutations(turn, artifact_dir), None, attached_detail_early, ""),
                "audit": f"blocked: {attached_detail_early}",
                "mutations": len(detect_mutations(turn, artifact_dir)),
                "claim": None,
                "case_r_wakeup": case_r_wakeup,
            }

    if re.search(r"black[- ]hat|CRITIC_VERDICT", seed, re.IGNORECASE):
        return allow("conversation seeded as a black-hat audit", case_r_wakeup=case_r_wakeup)

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

    if _is_isolated_swe_benchmark_turn(payload):
        swe_proof = has_post_mutation_local_test_proof(turn)
        if swe_proof.get("verified"):
            return allow(
                "isolated SWE_BENCHMARK_MODE verified by post-mutation local test execution",
                mutations=len(mutations),
                claim=claim,
            )

    proof_found, proof_detail, min_wave_idx = find_structural_proof_with_index(turn)
    if proof_found:
        critic_idx = last_critic_step_index(turn)
        guard_idx = critic_idx
        if min_wave_idx >= 0 and (guard_idx < 0 or min_wave_idx < guard_idx):
            guard_idx = min_wave_idx
        post_critic_mutations = (
            detect_mutations(turn[guard_idx + 1 :], artifact_dir) if guard_idx >= 0 else []
        )
        if post_critic_mutations:
            post_detail = (
                f"state mutated after goldfish/judge wave started ({', '.join(post_critic_mutations[:3])}); "
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
            "conversationId": get_str(payload, "conversationId", "conversation_id", "session_id"),
            "rootConversationId": get_str(payload, "rootConversationId", "root_conversation_id", "conversationId", "conversation_id", "session_id"),
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


def _strip_inline_backtick_spans(text: str) -> str:
    """Replaces single-line `inline code` spans so literal `<details>` or pipes do not trip prose parsers."""
    if not text:
        return ""
    return re.sub(r"(?<!`)`[^`\n]+`(?!`)", "code", text)


def check_c9_pre_prose_table_gate(turn_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """C9 Pre-Prose Table Gate (`G5a` >= 5-Row Floor)."""
    if not turn_steps:
        return {"passed": True, "reason": "No steps"}
    last_prose = ""
    for step in reversed(turn_steps):
        if step.get("type") == "PLANNER_RESPONSE" and step.get("content"):
            last_prose = str(step.get("content", ""))
            break
    sanitized_prose = _strip_inline_backtick_spans(last_prose)
    table_lines = [
        ln for ln in sanitized_prose.splitlines()
        if ln.strip().startswith("|") and ln.strip().endswith("|")
    ]
    if len(table_lines) < 5:
        return {
            "passed": True,
            "reason": "Below >= 5-row C9 table floor",
            "table_row_count": len(table_lines),
        }
    viewed_files: List[str] = []
    for step in turn_steps:
        for tc in (step.get("tool_calls") or []):
            if not isinstance(tc, dict):
                continue
            tname = tc.get("name")
            if tname in ("read_file", "view_file", "Read"):
                targs = _decode_args(tc.get("args"))
                p = str(targs.get("Path") or targs.get("AbsolutePath") or targs.get("file_path") or "")
                viewed_files.append(p)
    return {
        "passed": len(viewed_files) > 0,
        "table_row_count": len(table_lines),
        "viewed_files": viewed_files,
    }


def check_chat_bottom_up_tldr_structure(response_text: str) -> Dict[str, Any]:
    """Chat Bottom-Up Pyramid Gate (`G3` inline-backtick safe)."""
    words = response_text.split()
    if len(words) <= 120:
        return {"passed": True, "exempt": True, "word_count": len(words)}
    prose_no_fences = re.sub(r"```[\s\S]*?```", "", response_text)
    prose_safe = _strip_inline_backtick_spans(prose_no_fences)
    open_details = len(re.findall(r"<details\b[^>]*>", prose_safe, flags=re.IGNORECASE))
    close_details = len(re.findall(r"</details>", prose_safe, flags=re.IGNORECASE))
    details_balanced = open_details == close_details
    m = re.search(r"^###\s+⚡\s+TL;DR\b", response_text, flags=re.MULTILINE)
    if not m:
        return {
            "passed": False,
            "reason": "Missing '### ⚡ TL;DR' bottom section on response > 120 words",
            "details_balanced": details_balanced,
        }
    tail = response_text[m.end():]
    tail_clean = re.sub(r"`?CRITIC_VERDICT:.*$", "", tail, flags=re.MULTILINE).strip()
    has_code_below = "```" in tail_clean
    tail_safe = _strip_inline_backtick_spans(tail_clean)
    has_table_below = any(
        ln.strip().startswith("|") and ln.strip().endswith("|")
        for ln in tail_safe.splitlines()
    )
    tldr_words = len(tail_clean.split())
    passed = details_balanced and (not has_code_below) and (not has_table_below) and (tldr_words <= 95)
    return {
        "passed": passed,
        "tldr_word_count": tldr_words,
        "has_code_below": has_code_below,
        "has_table_below": has_table_below,
        "details_balanced": details_balanced,
    }


def audit_git_diff_test_tampering(diff_text: str) -> Dict[str, Any]:
    """Scans a unified git diff for reward-hacking test tampering."""
    deleted_asserts = 0
    added_asserts = 0
    added_skips = 0
    for line in diff_text.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-") and re.search(r"\b(assert|assertEqual|assertTrue|assertIn|assertRaises)\b", line):
            deleted_asserts += 1
        elif line.startswith("+") and re.search(r"\b(assert|assertEqual|assertTrue|assertIn|assertRaises)\b", line):
            added_asserts += 1
        elif line.startswith("+") and re.search(r"(@unittest\.skip|@pytest\.mark\.skip)", line):
            added_skips += 1
    tampered = (deleted_asserts > added_asserts and added_asserts == 0) or added_skips > 0
    return {
        "passed": not tampered,
        "deleted_asserts": deleted_asserts,
        "added_asserts": added_asserts,
        "added_skips": added_skips,
        "violation": "DELETED_ASSERTION_OR_SKIP" if tampered else None,
    }


def verify_subagent_proof_freshness(transcript_path: str, turn_start_epoch: float) -> bool:
    """Verifies that a subagent transcript file exists and was modified after turn_start_epoch."""
    if not transcript_path or not os.path.exists(transcript_path):
        return False
    try:
        return os.path.getmtime(transcript_path) >= (turn_start_epoch - 5.0)
    except OSError:
        return False


def detect_orphaned_background_tasks(turn_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """C14f Orphaned Background-Task & Non-Daemon Cron Livelock Guard."""
    unbounded_crons: List[str] = []
    background_cmds: List[str] = []
    killed_tasks: int = 0

    for step in turn_steps:
        for tc in step.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            name = str(tc.get("name") or "")
            args = _decode_args(tc.get("args"))
            if name == "schedule":
                cron_expr = str(args.get("CronExpression") or "").strip()
                is_daemon = bool(args.get("IsDaemon") is True)
                max_iter = args.get("MaxIterations")
                if cron_expr and not is_daemon and not (isinstance(max_iter, int) and max_iter > 0):
                    unbounded_crons.append(cron_expr)
            elif name == "run_command":
                is_daemon = bool(args.get("IsDaemon") is True)
                wait_ms = args.get("WaitMsBeforeAsync", 5000)
                cmd_line = str(args.get("CommandLine") or "")
                if not is_daemon and isinstance(wait_ms, int) and wait_ms <= 500 and "nohup" not in cmd_line:
                    background_cmds.append(cmd_line[:80])
            elif name == "manage_task" and str(args.get("Action") or "") == "kill":
                killed_tasks += 1

    active_orphans = max(0, len(background_cmds) - killed_tasks) + len(unbounded_crons)
    return {
        "passed": active_orphans == 0,
        "unbounded_crons": unbounded_crons,
        "background_commands_started": len(background_cmds),
        "tasks_killed": killed_tasks,
        "active_orphans": active_orphans,
    }


def format_compact_subagent_wakeup(
    summary_text: str, detail_path: str = "", max_bytes: int = 800
) -> Dict[str, Any]:
    """C14g Subagent Return Payload Cap (< 800 B)."""
    raw_bytes = len(summary_text.encode("utf-8"))
    if raw_bytes <= max_bytes:
        return {
            "passed": True,
            "wakeup_text": summary_text,
            "byte_length": raw_bytes,
            "truncated": False,
        }
    suffix = f"\n[Full dossier: {detail_path}]" if detail_path else "\n[Truncated to <800B]"
    budget = max(64, max_bytes - len(suffix.encode("utf-8")) - 3)
    clipped = summary_text.encode("utf-8")[:budget].decode("utf-8", errors="ignore").rstrip() + "..." + suffix
    return {
        "passed": len(clipped.encode("utf-8")) <= max_bytes,
        "wakeup_text": clipped,
        "byte_length": len(clipped.encode("utf-8")),
        "truncated": True,
    }


def enforce_shebang_exec_and_inmemory_compile(file_paths: List[str]) -> Dict[str, Any]:
    """AGW-W12-08 (`LL-2`): Sets `0o755` strictly on `#!` files and validates `.py` via in-memory `compile()`."""
    chmod_exec: List[str] = []
    chmod_cleared: List[str] = []
    compile_errors: List[str] = []

    for fpath in file_paths or []:
        if not fpath or not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "rb") as bf:
                head = bf.read(4)
            st_mode = os.stat(fpath).st_mode
            if head.startswith(b"#!"):
                if (st_mode & 0o111) != 0o111:
                    os.chmod(fpath, st_mode | 0o111)
                    chmod_exec.append(fpath)
            elif fpath.endswith((".md", ".json", ".txt", ".yaml", ".yml")) and (st_mode & 0o111):
                os.chmod(fpath, st_mode & ~0o111)
                chmod_cleared.append(fpath)
            if fpath.endswith(".py"):
                with open(fpath, "r", encoding="utf-8") as pf:
                    src = pf.read()
                compile(src, fpath, "exec")
        except SyntaxError as exc:
            compile_errors.append(f"{os.path.basename(fpath)}:{exc.lineno}: {exc.msg}")
        except Exception as exc:
            compile_errors.append(f"{os.path.basename(fpath)}: {exc!r}")

    return {
        "passed": len(compile_errors) == 0,
        "chmod_exec": chmod_exec,
        "chmod_cleared": chmod_cleared,
        "compile_errors": compile_errors,
    }


def has_post_mutation_local_test_proof(turn_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """AGW-W12-13 (`NONDEV-BUG-7`): Scans for passing local test execution at or after last file mutation."""
    last_mut_idx = -1
    for idx, step in enumerate(turn_steps or []):
        for tc in step.get("tool_calls") or []:
            if isinstance(tc, dict) and tc.get("name") in FILE_MUTATING_TOOLS:
                last_mut_idx = idx

    test_cmd_re = re.compile(r"\b(pytest|unittest|--self-test|verify_skill_end_state|test_)\b", re.IGNORECASE)
    matched_commands: List[str] = []
    passing_outputs: int = 0

    scan_slice = (turn_steps or [])[max(0, last_mut_idx) :]
    for step in scan_slice:
        for tc in step.get("tool_calls") or []:
            if isinstance(tc, dict) and tc.get("name") in ("run_command", "Bash", "bash"):
                cmd = str(_decode_args(tc.get("args")).get("CommandLine") or _decode_args(tc.get("args")).get("command") or "")
                if test_cmd_re.search(cmd):
                    matched_commands.append(cmd[:120])
        content = str(step.get("content") or "")
        if re.search(r"\b(OK|PASSED|passed|exit_code[\"':\s]+0|verdict[\"':\s]+PASS)\b", content):
            passing_outputs += 1

    verified = len(matched_commands) > 0 and passing_outputs > 0
    return {
        "verified": verified,
        "last_mutation_step": last_mut_idx,
        "matched_test_commands": matched_commands,
        "passing_outputs": passing_outputs,
    }


if __name__ == "__main__":
    main()
