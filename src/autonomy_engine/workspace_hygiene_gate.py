#!/usr/bin/env python3
"""Workspace Hygiene Gate (`workspace_hygiene_gate.py`).
Audits workspace directories for orphaned `.bak` files, temporary scratch clutter,
and broken symlinks during Nightly Dreaming housekeeping.
"""
import json
import os
from typing import Any, Dict, List


def audit_workspace_hygiene(root_dir: str) -> Dict[str, Any]:
    bak_files: List[str] = []
    broken_symlinks: List[str] = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", "venv")]
        for fname in files:
            fpath = os.path.join(root, fname)
            if os.path.islink(fpath) and not os.path.exists(fpath):
                broken_symlinks.append(fpath)
            elif fname.endswith(".bak") or fname.endswith("~"):
                bak_files.append(fpath)
    return {
        "status": "clean" if (not bak_files and not broken_symlinks) else "needs_cleanup",
        "bak_files_count": len(bak_files),
        "broken_symlinks_count": len(broken_symlinks),
        "bak_files": bak_files[:25],
        "broken_symlinks": broken_symlinks[:25],
    }


if __name__ == "__main__":
    print(json.dumps(audit_workspace_hygiene(os.getcwd()), indent=2))
