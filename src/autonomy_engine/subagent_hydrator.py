import json
import math
import hashlib
import sqlite3
import os
from typing import Dict, Any, List, Optional

class SubagentContextHydrator:
    def __init__(self, cache_db_path: str = "/tmp/antigravity_action_cache.db", base_budget: int = 2500):
        self.cache_db_path = cache_db_path
        self.base_budget = base_budget
        self._init_cache_db()

    def _init_cache_db(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.cache_db_path)), exist_ok=True)
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS action_cache (
                    action_hash TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    canonical_args TEXT NOT NULL,
                    cached_result TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
            """)
            conn.commit()

    def calculate_adaptive_budget(self, task_description: str, role_multiplier: float = 1.0, depth: int = 1) -> int:
        words = task_description.split()
        unique_ratio = len(set(words)) / max(len(words), 1)
        entropy_factor = max(0.5, min(2.0, unique_ratio * 1.5))
        depth_scaling = 1.0 + 0.40 * math.log(1 + depth)
        raw_budget = self.base_budget * (entropy_factor ** 0.70) * role_multiplier * depth_scaling
        return int(max(800, min(8000, raw_budget)))

    def hydrate_context_envelope(self, role: str, task_description: str, core_payload: str, resource_pointers: List[str], depth: int = 1) -> str:
        budget = self.calculate_adaptive_budget(task_description, depth=depth)

        pillar1_invariants = (
            f"<invariants>\n"
            f"  <role>{role}</role>\n"
            f"  <sandbox_mode>isolated_branch</sandbox_mode>\n"
            f"  <max_recursion_depth>1</max_recursion_depth>\n"
            f"  <typography>clean_unicode_no_raw_latex</typography>\n"
            f"</invariants>"
        )

        p3_lines = "\n".join(f"  <resource>{p}</resource>" for p in resource_pointers)
        pillar3_manifest = f"<resource_manifest>\n{p3_lines}\n</resource_manifest>"

        # Allocate remaining budget to core payload
        used_len = len(pillar1_invariants) + len(pillar3_manifest) + 100
        avail_payload_budget = max(400, budget - used_len)
        truncated_payload = core_payload[:avail_payload_budget]

        envelope = (
            f"<hydrated_context budget=\"{budget}\">\n"
            f"{pillar1_invariants}\n"
            f"<core_payload>\n{truncated_payload}\n</core_payload>\n"
            f"{pillar3_manifest}\n"
            f"</hydrated_context>"
        )
        return envelope

    def get_action_cache(self, tool_name: str, args: Dict[str, Any]) -> Optional[str]:
        canon_args = json.dumps(args, sort_keys=True)
        action_hash = hashlib.sha256(f"{tool_name}:{canon_args}".encode("utf-8")).hexdigest()
        with sqlite3.connect(self.cache_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cached_result FROM action_cache WHERE action_hash = ?", (action_hash,))
            row = cursor.fetchone()
            if row:
                return row[0]
        return None

    def put_action_cache(self, tool_name: str, args: Dict[str, Any], result: str) -> None:
        import time
        canon_args = json.dumps(args, sort_keys=True)
        action_hash = hashlib.sha256(f"{tool_name}:{canon_args}".encode("utf-8")).hexdigest()
        with sqlite3.connect(self.cache_db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO action_cache (action_hash, tool_name, canonical_args, cached_result, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (action_hash, tool_name, canon_args, result, time.time()))
            conn.commit()
