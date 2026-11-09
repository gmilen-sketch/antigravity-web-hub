"""Rule: Destructive Command Interceptor (`force_ask` Enterprise Policy Mediation).

Prevents unconfirmed execution of high-blast-radius destructive commands even
when the agent runs under auto-execution / Turbo mode (`decision = "force_ask"`),
while exempting ephemeral `/tmp` and `/dev/shm` scratch cleanup targets.
"""

import re
from typing import Optional

_RM_RECURSIVE_RE = re.compile(
    r"\brm\s+(?:-[a-zA-Z]*(?:r[a-zA-Z]*f|f[a-zA-Z]*r)[a-zA-Z]*\b"
    r"|(?=[^\n;|&]*--recursive)(?=[^\n;|&]*--force)[^\n;|&]+)",
    re.IGNORECASE,
)

PATTERNS = [
    (r"\bgit\s+reset\s+--hard\b", "Destructive git working tree reset"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f\b", "Untracked file purge (git clean -f)"),
    (r"\bbq\s+rm\b", "BigQuery dataset/table deletion (bq rm)"),
    (
        r"\bgcloud\b[^\n;|&]*\b(?:delete|remove-iam-policy-binding|set-iam-policy)\b",
        "Destructive or IAM-mutating gcloud operation",
    ),
    (r"\bkubectl\s+delete\b", "Kubernetes resource deletion (kubectl delete)"),
    (r"\bterraform\s+destroy\b", "Terraform infrastructure teardown"),
    (r"\bdrop\s+database\b", "Database drop"),
    (r"\bdrop\s+table\b", "Table drop"),
    (r"\btruncate\s+table\b", "Table truncation"),
    (r"\bmkfs\b", "Filesystem formatting"),
    (r"\bdd\s+if=.*of=/dev/", "Raw disk write"),
]


def _is_ephemeral_scratch_rm_only(segment: str) -> bool:
    """Returns True when every non-flag path operand of an `rm` segment stays strictly inside `/tmp/` or `/dev/shm/`."""
    tokens = segment.strip().split()
    try:
        rm_idx = next(i for i, tok in enumerate(tokens) if tok == "rm" or tok.endswith("/rm"))
    except StopIteration:
        return False
    operands = [t.strip("\"'") for t in tokens[rm_idx + 1 :] if t and not t.startswith("-")]
    if not operands:
        return False
    for op in operands:
        if ".." in op or "$" in op or "`" in op:
            return False
        if not (op.startswith("/tmp/") or op.startswith("/dev/shm/")):
            return False
    return True


def check(tool: str, args: dict, ctx: dict | None = None) -> Optional[dict]:
    if tool != "run_command":
        return None
    cmd = str(args.get("CommandLine") or args.get("command") or "")
    if not cmd:
        return None

    for seg in re.split(r"(?:&&|\|\||[;\n|])", cmd):
        m_rm = _RM_RECURSIVE_RE.search(seg)
        if m_rm and not _is_ephemeral_scratch_rm_only(seg):
            return {
                "decision": "force_ask",
                "reason": (
                    f"High-risk destructive command detected: '{m_rm.group(0).strip()}' "
                    "(Unbounded recursive deletion outside /tmp or /dev/shm). Explicit human confirmation required."
                ),
            }

    for pat, desc in PATTERNS:
        m = re.search(pat, cmd, re.IGNORECASE)
        if m:
            return {
                "decision": "force_ask",
                "reason": f"High-risk destructive command detected: '{m.group(0)}' ({desc}). Explicit human confirmation required.",
            }
    return None


check_destructive_commands = check

