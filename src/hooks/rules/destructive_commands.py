"""Rule: Destructive Command Interceptor.
Prevents unconfirmed execution of high-blast-radius destructive commands.
"""
import re

PATTERNS = [
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b", "Unbounded recursive directory deletion (rm -rf)"),
    (r"\bgit\s+reset\s+--hard\b", "Destructive git working tree reset"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f\b", "Untracked file purge (git clean -f)"),
    (r"\bdrop\s+database\b", "Database drop"),
    (r"\bdrop\s+table\b", "Table drop"),
    (r"\btruncate\s+table\b", "Table truncation"),
    (r"\bmkfs\b", "Filesystem formatting"),
    (r"\bdd\s+if=.*of=/dev/", "Raw disk write"),
]


def check(tool: str, args: dict, ctx: dict) -> dict | None:
    if tool != "run_command":
        return None
    cmd = str(args.get("CommandLine", ""))
    if not cmd:
        return None
    for pat, desc in PATTERNS:
        m = re.search(pat, cmd, re.IGNORECASE)
        if m:
            return {
                "decision": "ask",
                "reason": f"High-risk destructive command detected: '{m.group(0)}' ({desc}). Explicit user confirmation required.",
            }
    return None
