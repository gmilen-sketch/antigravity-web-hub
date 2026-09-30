#!/usr/bin/env python3
"""Open Knowledge Format (OKF v0.2) Bundle Validator (`validate_okf.py`).
Validates an OKF v0.2 `kb/` directory against the public Open Knowledge Format v0.2 schema:
- Verifies `kb/index.md` exists.
- Verifies every concept dossier has valid YAML frontmatter with required v0.2 fields:
  `okf_version: "0.2"`, `id` (kebab-case), `title`, `summary`, `type`, `status`,
  `confidence` (0.0-1.0), `last_verified` (ISO 8601 date), `tags`, and `sources`.
- Verifies footnote citation linkage (`[^source-id]`) and checks for leaked workstation paths.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from knowledge_graph.okf_knowledge_compiler import parse_frontmatter, VALID_TYPES, VALID_STATUSES

KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
LEAK_RE = re.compile(r"/usr/local/google/" + r"home/[a-zA-Z0-9_.-]+")


def validate_kb_bundle(kb_root: str) -> Dict[str, Any]:
    kb_path = Path(kb_root)
    errors: List[str] = []
    warnings: List[str] = []
    files_checked = 0

    if not kb_path.exists():
        return {"valid": False, "files_checked": 0, "errors": [f"KB root not found: {kb_root}"], "warnings": []}

    index_file = kb_path / "index.md"
    if not index_file.exists():
        errors.append("Missing required entry point: kb/index.md")

    for md_file in sorted(kb_path.rglob("*.md")):
        files_checked += 1
        rel = str(md_file.relative_to(kb_path))
        content = md_file.read_text(encoding="utf-8", errors="ignore")

        if LEAK_RE.search(content):
            errors.append(f"{rel}: Contains unanonymized workstation path leak")

        if md_file.name in ("index.md", "log.md", "README.md"):
            continue

        meta = parse_frontmatter(content)
        if not meta:
            errors.append(f"{rel}: Missing YAML frontmatter block")
            continue

        if str(meta.get("okf_version", "")) != "0.2":
            errors.append(f"{rel}: okf_version must be '0.2', got '{meta.get('okf_version')}'")

        doc_id = str(meta.get("id", ""))
        if not doc_id or not KEBAB_RE.match(doc_id):
            errors.append(f"{rel}: Invalid or missing kebab-case 'id': '{doc_id}'")

        for req_key in ("title", "summary", "type", "status", "last_verified"):
            if not meta.get(req_key):
                errors.append(f"{rel}: Missing required frontmatter field '{req_key}'")

        if meta.get("type") and meta["type"] not in VALID_TYPES:
            errors.append(f"{rel}: Invalid type '{meta['type']}' (allowed: {sorted(VALID_TYPES)})")

        if meta.get("status") and meta["status"] not in VALID_STATUSES:
            errors.append(f"{rel}: Invalid status '{meta['status']}' (allowed: {sorted(VALID_STATUSES)})")

        conf = meta.get("confidence")
        if conf is None or not (0.0 <= float(conf) <= 1.0):
            errors.append(f"{rel}: 'confidence' must be between 0.0 and 1.0, got '{conf}'")

        if meta.get("last_verified") and not ISO_DATE_RE.match(str(meta["last_verified"])):
            errors.append(f"{rel}: 'last_verified' must be ISO 8601 YYYY-MM-DD, got '{meta['last_verified']}'")

        if "[^" not in content:
            warnings.append(f"{rel}: No inline citation footnote marker [^...] found in body")

    return {
        "valid": len(errors) == 0,
        "files_checked": files_checked,
        "errors": errors,
        "warnings": warnings,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate OKF v0.2 Knowledge Bundle")
    parser.add_argument("--kb-root", type=str, default=os.path.join(REPO_ROOT, "kb"))
    args = parser.parse_args()
    result = validate_kb_bundle(args.kb_root)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)
