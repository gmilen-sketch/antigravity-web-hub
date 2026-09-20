#!/usr/bin/env python3
"""
Standalone Black Hat Forensic Analyzer v2.0 (Clean-Room Standalone Edition).
Validates Python AST syntax, JSON files, and checks for leaked workstation paths
or proprietary internal identifiers.
"""

import ast
import os
import re
import sys
import json
import argparse
from typing import Dict, Any, List

PROHIBITED_LEAK_PATTERNS = [
    (r"/usr/local/google/home/[A-Za-z0-9_.-]+", "Hardcoded workstation home directory"),
    (r"sso://", "Internal SSO git scheme"),
    (r"\.corp\.google\.com", "Internal corporate domain"),
]


def scan_target(target_path: str) -> Dict[str, Any]:
    py_files_checked = 0
    json_files_checked = 0
    syntax_errors: List[str] = []
    path_leaks: List[str] = []

    if os.path.isfile(target_path):
        files_to_scan = [target_path]
    else:
        files_to_scan = []
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", "venv", "bin", "assets")]
            for fname in files:
                files_to_scan.append(os.path.join(root, fname))

    for fpath in files_to_scan:
        if os.path.abspath(fpath) == os.path.abspath(__file__):
            continue
        ext = os.path.splitext(fpath)[1].lower()
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        if ext == ".py":
            py_files_checked += 1
            try:
                ast.parse(content, filename=fpath)
            except SyntaxError as exc:
                syntax_errors.append(f"{fpath}:{exc.lineno}: {exc.msg}")
        elif ext == ".json":
            json_files_checked += 1
            try:
                json.loads(content)
            except Exception as exc:
                syntax_errors.append(f"{fpath}: JSON error: {exc}")

        if ext in (".py", ".js", ".sh", ".json"):
            for pattern, desc in PROHIBITED_LEAK_PATTERNS:
                if re.search(pattern, content):
                    path_leaks.append(f"{fpath}: {desc}")

    verdict = "PASS" if (not syntax_errors and not path_leaks) else "FAIL"
    return {
        "verdict": verdict,
        "py_files_checked": py_files_checked,
        "json_files_checked": json_files_checked,
        "syntax_errors": syntax_errors,
        "path_leaks": path_leaks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Hat Forensic Analyzer v2.0")
    parser.add_argument("--target", type=str, required=True, help="Target file or directory to audit")
    args = parser.parse_args()
    res = scan_target(args.target)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
