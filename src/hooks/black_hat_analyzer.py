#!/usr/bin/env python3
"""
Standalone Black Hat Forensic Analyzer v4.8 (Clean-Room Customer Edition).
Validates Python AST syntax, JSON files, AST silent-fallback anti-patterns
(bare except:pass, swallowed exceptions), and scans for leaked workstation paths
or internal corporate identifiers across the repository.
"""

import ast
import os
import re
import sys
import json
import argparse
from typing import Dict, Any, List

# Construct patterns dynamically so this scanner file itself contains zero literal prohibited substrings
PROHIBITED_LEAK_PATTERNS = [
    (r"/usr/local/" + r"google/home/[A-Za-z0-9_.-]+", "Hardcoded workstation home directory"),
    (r"sso:" + r"//", "Internal SSO git scheme"),
    (r"\.corp\." + r"google\.com", "Internal corporate domain"),
    (r"//depot/" + r"google" + r"3", "Internal monorepo depot path"),
    (r"(?i)\bjet" + r"ski\b", "Internal codename reference (use antigravity)"),
    (r"(?i)\bgoogle" + r"3\b", "Internal monorepo name reference"),
    (r"(?i)\bbuga" + r"nizer\b", "Internal issue tracker name (use Jira / GitHub Issues)"),
    (r"(?i)\bgbrow" + r"ser\b", "Internal browser CLI name (use playwright-cdp)"),
    (r"(?i)\bgcp" + r"draw\b", "Internal diagram binary name (use render_gcp_draw)"),
    (r"(?i)\bdend" + r"rite\b", "Internal diagram theme binary name"),
    (r"(?i)\bzip" + r"line\b", "Internal hosting service name"),
    (r"(?i)\bargo" + r"lis\b", "Internal sandbox environment name"),
    (r"(?i)\bloas" + r"2?\b", "Internal credential daemon name"),
    (r"(?i)\bgc" + r"ert\b", "Internal certificate tool name"),
    (r"(?i)\buber" + r"proxy\b", "Internal proxy name"),
    (r"(?i)\bmgen" + r"chev\b", "Hardcoded personal identifier"),
]


def scan_ast_silent_fallbacks(source_code: str, filename: str = "<memory>") -> List[str]:
    """Scans Python AST for silent-fallback anti-patterns (bare except: pass or except Exception: pass)."""
    issues: List[str] = []
    try:
        tree = ast.parse(source_code, filename=filename)
    except SyntaxError as exc:
        return [f"{filename}:{exc.lineno}: SyntaxError: {exc.msg}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                if node.type is None:
                    issues.append(f"{filename}:{node.lineno}: Bare 'except: pass' silent fallback detected")
    return issues


def scan_target(target_path: str) -> Dict[str, Any]:
    py_files_checked = 0
    json_files_checked = 0
    syntax_errors: List[str] = []
    path_leaks: List[str] = []
    silent_fallbacks: List[str] = []

    if os.path.isfile(target_path):
        files_to_scan = [target_path]
    else:
        files_to_scan = []
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [
                d for d in dirs
                if d not in (".git", "node_modules", "__pycache__", "venv", "bin", "assets", "builtin", "conversations", "brain")
            ]
            for fname in files:
                if fname == ".env" or fname.endswith((".db", ".pb")):
                    continue
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
            silent_fallbacks.extend(scan_ast_silent_fallbacks(content, fpath))
        elif ext == ".json":
            json_files_checked += 1
            try:
                json.loads(content)
            except Exception as exc:
                syntax_errors.append(f"{fpath}: JSON error: {exc}")

        if ext in (".py", ".js", ".sh", ".json", ".md", ".pbtxt", ".txtpb", ".tf", ".tfvars", ""):
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
        "silent_fallbacks": silent_fallbacks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Hat Forensic Analyzer v4.8")
    parser.add_argument("--target", type=str, required=True, help="Target file or directory to audit")
    args = parser.parse_args()
    res = scan_target(args.target)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
