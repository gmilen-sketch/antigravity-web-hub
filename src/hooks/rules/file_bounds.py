"""Rule: View File Bounding & Range Clamping.
Clamps oversized view_file requests to prevent accidental context blowups.
"""
import os

MAX_WINDOW = 800


def check(tool: str, args: dict, ctx: dict) -> dict | None:
    if tool != "view_file":
        return None
    path = args.get("AbsolutePath", "")
    if not path or not os.path.isfile(path):
        return None

    start = args.get("StartLine")
    end = args.get("EndLine")

    if start is not None and end is not None:
        if end - start + 1 > MAX_WINDOW:
            return {
                "decision": "allow",
                "overwrite": {
                    "StartLine": start,
                    "EndLine": start + MAX_WINDOW - 1,
                },
                "reason": f"Range ({start}-{end}) exceeds maximum window {MAX_WINDOW}. Clamped to {MAX_WINDOW} lines.",
            }
        return None

    try:
        with open(path, "rb") as f:
            line_count = sum(1 for _ in f)
    except Exception:
        return None

    if line_count > MAX_WINDOW:
        s = start if start is not None else 1
        e = min(s + MAX_WINDOW - 1, line_count)
        return {
            "decision": "allow",
            "overwrite": {
                "StartLine": s,
                "EndLine": e,
            },
            "reason": f"File has {line_count} lines (> {MAX_WINDOW}). Clamped to lines {s}-{e} to prevent token flood.",
        }

    return None
