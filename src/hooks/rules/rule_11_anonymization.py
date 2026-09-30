"""Rule 11: Workstation Path and Identity Anonymization Mandate.
Traps hardcoded home workstation paths in shared artifacts and code.
"""
import os
import re

RAW_HOME_PATTERN = re.compile(
    r"/usr/local/google/" + r"home/[a-zA-Z0-9_\-]+",
    re.IGNORECASE,
)

EXCLUDED_PATH_SUBSTRINGS = [
    "/tmp/",
    "/.system_generated/",
    "/telemetry/",
    "/cache/",
]


def check(tool: str, args: dict, ctx: dict) -> dict | None:
    if tool not in ("write_to_file", "replace_file_content"):
        return None

    target = args.get("TargetFile", "")
    if any(ex in target for ex in EXCLUDED_PATH_SUBSTRINGS):
        return None

    blob = str(args.get("CodeContent", "")) + "\n" + str(args.get("ReplacementContent", ""))
    if not blob.strip():
        return None

    match = RAW_HOME_PATTERN.search(blob)
    if match:
        matched_str = match.group(0)
        if "<USER_HOME_DIR>" not in matched_str:
            return {
                "decision": "deny",
                "reason": (
                    f"Rule 11 violation: Unanonymized workstation path '{matched_str}' detected in payload for '{os.path.basename(target)}'. "
                    f"Replace with '<USER_HOME_DIR>' or '<USER_LDAP>' per Sentinel protocols."
                ),
            }

    return None
