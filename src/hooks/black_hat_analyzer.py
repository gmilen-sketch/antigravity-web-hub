#!/usr/bin/env python3
"""
Standalone Black Hat Forensic Analyzer v4.8 (Clean-Room Customer Edition).
Validates Python AST syntax, JSON files, AST silent-fallback anti-patterns
(bare except:pass, swallowed exceptions), and scans for leaked workstation paths,
hardcoded credentials, or prohibited internal token SHA-256 digests across the repository.
"""

import ast
import hashlib
import os
import re
import sys
import json
import argparse
from typing import Dict, Any, List

PROHIBITED_LEAK_PATTERNS = [
    (r"\bAKIA[0-9A-Z]{16}\b", "Hardcoded AWS access key ID"),
    (r"\bghp_[A-Za-z0-9_]{20,}\b", "Hardcoded GitHub personal access token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", "Hardcoded GitHub fine-grained token"),
    (r"\bAIza[0-9A-Za-z\-_]{35}\b", "Hardcoded Google Cloud API key"),
]

# One-way SHA-256 digests of prohibited internal codenames, tool names, and personal identifiers
PROHIBITED_TOKEN_SHA256 = {
    "9918f0455cefecd78b99a6d8daf7da74732ccd50fdbafda860ecc0f050f2e725",
    "acc601c59448a3dc1f88eb9c889fedbdbd7d6465a1b5702fbd16b70a41280d8d",
    "7287afc74731c5aa749600569b97735f06e83c1faf1c7b7becc07a5e9a158cc6",
    "546f028dac5bbe1b967cdb7009e03526d5ff2a29885e5d838d8599fefd46fad0",
    "13da8580ec41963d03186bcd3edabd5b6868ac65721b8b05009742f4132e493c",
    "05bc6fa1ff0770f5de13c86f1d27418c938adea2dac09bf99680e8c31bf89c1c",
    "e134c033e88fbff499696afe2aa8744805969081fb2ef10369661c3e640082eb",
    "d5b7b23e6461293a8a2b4e12c8dfbfa394e39f091f567b11f66b9baa3fc8e338",
    "d6bf0ec06b18bfc5489033c22bc53e15ded58840c85525b4df87eafb4ac2bb4c",
    "34f62330dab329804641a03da8056ae7a71e0010b541adef9dffbd0eda773ef8",
    "e1aafe66299f163ec01243b2ac0281f3023a809ab5ca9ed935328a05ac04e7ce",
    "80f400c0518cd218b0c5af99959e5e35797ac378ffd72b55944132fd43d710a3",
    "1ea9ccb8657801321ad969f574d3de77c1c466647844bf418645d88f2d8b368c",
    "d291cb308c2e1d8ce9a65444ad1551243bdfe5df9033e0ec81c0b3ba6b4ed670",
    "2d46d9e693ae13a9c49e2e5689354847f2c9f2bcfea49f863ab762bf1fdf7582",
    "f0ab296ac531c989a60fd0019c703a22e7af90ae83a10cb764679fd7f4c70ca7",
    "fcc72010527a8b1e70484b3d4de133ad8db9055754d18a945a894a945f3d5cc1",
    "a993841015c2bd443458d35c51d2869d1dda3580d514143ec2f1f5b0aa8ec982",
    "96839b38daa19348e9b64431fe2a124c03c8b3fd64b53c1091218d952e621818",
    "a2ccd9890912865ac499d9f9144df1a55649485311c724d8389370a19e2fec0d",
    "58c942cd4ea1cbf7199a5faf099f2bf6bf1ed6a6735633e156ba35cb461c7a4e",
    "b9c6505df56123cfa556c00c2bd30dc0607c33505d579a1babe1a351ca1db7e8",
    "e3652ee763affcd38977b3519dcc1d0920b5348a6dea2e1739a91a572d271226",
    "3b3387b96d92bcc780d9e58b0c2845b07734a21ce41b8ff91c92ad24b720eb80",
    "e115702a38a06500983c7efddc8abcb17c5fa9a016ee1da0a86facc86f4b05d9",
    "cebb544920c67648fd45a2a4aa536eb7bc50ad1f7506eaa85d762f8f32915981",
    "5f8943ba9f5820644ded25d08cef7c4ec1d6bd1e857d68d7cd21c5cb22f3069a",
    "a63e3cd33fd7d9aeadaa209e754caa59b6134410dbfdb3921de04d110417d5ab",
    "55b5b346f53e638ca35ae0519f458c5f46308b98f6979a9719b4d0cac7f43f42",
    "068425c4fdd03f5fce5df0b3acef6750c138f40b730ec057c1b410cf34cb046d",
    "d43e610ed1d8b1bdf2fc1d636d5db802e331d6c3e8467e65f26b1ed874f5ad55",
    "2e2943ed09299b1cecb996822bba5e6cebc97f30f3be8172cfa69d391274f079",
    "dbf0759caae83fe9f0d8c35c56f7bffb35d8b7a9b40ac612ecbc06e84b924fff",
    "f4cdde86ce9ba1f27679ca97cd4412ffb8cbb02716a6f066339130d554160baf",
}


def scan_ast_silent_fallbacks(source_code: str, filename: str = "<memory>") -> List[str]:
    """Scans Python AST for silent-fallback anti-patterns (bare except: pass)."""
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
                if fname in (".env", "HANDOVER.md", "PROMPTS_HISTORY.md") or fname.endswith((".db", ".pb")):
                    continue
                files_to_scan.append(os.path.join(root, fname))

    home_dir = os.path.expanduser("~")
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
            if home_dir and len(home_dir) > 6 and home_dir in content:
                path_leaks.append(f"{fpath}: Hardcoded workstation home directory")
            for pattern, desc in PROHIBITED_LEAK_PATTERNS:
                if re.search(pattern, content):
                    path_leaks.append(f"{fpath}: {desc}")
            for token in set(re.findall(r"[A-Za-z0-9_-]{4,}", content)):
                h = hashlib.sha256(token.lower().encode("utf-8")).hexdigest()
                if h in PROHIBITED_TOKEN_SHA256:
                    path_leaks.append(f"{fpath}: Prohibited token '{token}'")

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
