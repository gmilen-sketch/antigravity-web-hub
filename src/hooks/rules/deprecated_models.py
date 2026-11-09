"""Rule 28: Deprecated / Prohibited Model detector.

Blocks invocation or configuration of retired or prohibited model slugs across
both native (`write_file`, `edit_file`) and legacy (`write_to_file`,
`replace_file_content`) file-mutation and shell tools.
"""

import re

BANNED = {
    r"\bgemini-1" + r"\.[05][-\w]*": "gemini-3.8-flash",
    r"\bgemini-2" + r"\.0-flash[-\w]*": "gemini-3.8-flash",
    r"\bgemini-2" + r"\.5-flash\b": "gemini-3.8-flash",
    r"\bgemini-2" + r"\.5-pro\b": "gemini-4-argon",
    r"\bgemini-3" + r"\.5-pro\b": "gemini-4-argon",
    r"\bgemini-3" + r"\.7-flash\b": "gemini-3.8-flash",
    r"\b(text|chat|code)-" + r"bison[-\w]*": "gemini-3.8-flash",
    r"\btextembedding-" + r"gecko[-\w]*": "gemini-embedding-001",
    r"\btext-embedding-00" + r"[45]\b": "gemini-embedding-001",
    r"\bclaude-(1|2|3-0|3-5-" + r"sonnet|3-5-haiku|3-7-sonnet)[-\w]*": "claude-sonnet-5-5",
    r"\bclaude-(?:opus|sonnet)-" + r"4(?:-[0-9]+)?\b": "claude-opus-5-5",
}

WRITE_AND_EXEC_TOOLS = frozenset({
    "write_file",
    "edit_file",
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
    "run_command",
})

FIELDS = ("Content", "Replacement", "CodeContent", "ReplacementContent", "CommandLine", "command")


def check(tool: str, args: dict, ctx: dict | None = None) -> dict | None:
    if tool not in WRITE_AND_EXEC_TOOLS:
        return None
    blob = "\n".join(str(args.get(f, "")) for f in FIELDS if args.get(f))
    if not blob:
        return None
    for pat, successor in BANNED.items():
        m = re.search(pat, blob, re.IGNORECASE)
        if m:
            return {
                "decision": "deny",
                "reason": (
                    f"Rule 28 violation: '{m.group(0)}' is deprecated or retired. "
                    f"Recommended GA successor: '{successor}'. Verify against active Vertex AI Model Garden "
                    f"endpoints before deploying."
                ),
            }
    return None
