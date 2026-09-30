"""Rule 28: Deprecated / Prohibited Model detector.
Blocks invocation or configuration of deprecated model slugs across write/command tools.
"""
import re

BANNED = {
    r"\bgemini-1" + r"\.5[-\w]*": "gemini-3.8-flash",
    r"\bgemini-2" + r"\.0-flash[-\w]*": "gemini-3.8-flash",
    r"\bgemini-2" + r"\.5-flash\b": "gemini-3.8-flash",
    r"\bgemini-2" + r"\.5-pro\b": "gemini-3.5-pro",
    r"\b(text|chat|code)-" + r"bison[-\w]*": "gemini-3.8-flash",
    r"\btextembedding-" + r"gecko[-\w]*": "gemini-embedding-001",
    r"\btext-embedding-00" + r"[45]\b": "gemini-embedding-001",
    r"\bclaude-(1|2|3-0|3-5-" + r"sonnet|3-5-haiku)[-\w]*": "claude-opus-5",
}

FIELDS = ("CodeContent", "ReplacementContent", "CommandLine")


def check(tool: str, args: dict, ctx: dict) -> dict | None:
    if tool not in ("write_to_file", "replace_file_content", "run_command"):
        return None
    blob = "\n".join(str(args.get(f, "")) for f in FIELDS)
    if not blob:
        return None
    for pat, successor in BANNED.items():
        m = re.search(pat, blob, re.IGNORECASE)
        if m:
            return {
                "decision": "deny",
                "reason": (
                    f"Rule 28 violation: '{m.group(0)}' is deprecated or prohibited. "
                    f"Recommended successor: '{successor}'. Verify against active Model Garden "
                    f"endpoints before deploying."
                ),
            }
    return None
