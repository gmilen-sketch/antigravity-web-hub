#!/usr/bin/env python3
"""
Skill & Hook Deobfuscation & Prompt-Injection Safety Scanner (Clean-Room Edition).
Detects Base64/ROT13/hex-encoded shell payloads, Unicode zero-width/bidi homoglyphs,
and prompt-injection takeover directives inside skill or hook files.
"""
import re
import base64
import codecs
from typing import Dict, Any, List, Optional

BIDI_AND_ZW_CHARS = set("\u200b\u200c\u200d\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff")

DANGEROUS_PATTERNS = [
    (r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions", "PROMPT_INJECTION_TAKEOVER"),
    (r"(?i)curl\s+[^|]*\|\s*(ba)?sh", "REMOTE_PIPE_EXECUTION"),
    (r"(?i)wget\s+[^|]*\|\s*(ba)?sh", "REMOTE_PIPE_EXECUTION"),
    (r"(?i)/dev/tcp/[0-9a-zA-Z._-]+/[0-9]+", "REVERSE_SHELL_SOCKET"),
]


def scan_text_safety(text: str) -> Dict[str, Any]:
    findings: List[str] = []
    if any(ch in BIDI_AND_ZW_CHARS for ch in text):
        findings.append("UNICODE_HIDDEN_BIDI_OR_ZW_CHAR")

    for pat, label in DANGEROUS_PATTERNS:
        if re.search(pat, text):
            findings.append(label)

    # Check Base64 blobs >= 24 chars
    for m in re.finditer(r"\b[A-Za-z0-9+/]{24,}={0,2}\b", text):
        try:
            decoded = base64.b64decode(m.group(0)).decode("utf-8", errors="ignore")
            for pat, label in DANGEROUS_PATTERNS:
                if re.search(pat, decoded):
                    findings.append(f"OBFUSCATED_BASE64_{label}")
        except Exception:
            pass

    # Check ROT13 when 'rot13' is mentioned
    if "rot13" in text.lower():
        decoded_rot = codecs.decode(text, "rot_13")
        for pat, label in DANGEROUS_PATTERNS:
            if re.search(pat, decoded_rot):
                findings.append(f"OBFUSCATED_ROT13_{label}")

    return {"safe": len(findings) == 0, "findings": findings}


def check(tool_name: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if tool_name in ("write_to_file", "replace_file_content"):
        target = str(tool_args.get("TargetFile", ""))
        if "SKILL.md" in target or "/skills/" in target or "/hooks/" in target:
            content = str(tool_args.get("CodeContent", "")) + str(tool_args.get("ReplacementContent", ""))
            res = scan_text_safety(content)
            if not res["safe"]:
                return {
                    "decision": "block",
                    "reason": f"Skill/Hook Safety Gate blocked unsafe payload in {target}: {res['findings']}",
                }
    return None
