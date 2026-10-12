#!/usr/bin/env python3
"""
Pre-Mutation Copy-on-Write Snapshot & Rollback Guard v2.0 (Clean-Room Edition).
Creates lightweight tar.gz backups before destructive directory or config mutations.
"""

import os
import shutil
import tarfile
import tempfile
from typing import Dict, Any


def create_snapshot(target_path: str, snapshot_dir: str = None) -> Dict[str, Any]:
    snapshot_dir = snapshot_dir or tempfile.gettempdir()
    os.makedirs(snapshot_dir, exist_ok=True)
    base = os.path.basename(os.path.abspath(target_path)) or "workspace"
    archive_path = os.path.join(snapshot_dir, f"antigravity_snapshot_{base}.tar.gz")
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(target_path, arcname=base)
    return {"status": "ok", "snapshot_archive": archive_path, "bytes": os.path.getsize(archive_path)}
