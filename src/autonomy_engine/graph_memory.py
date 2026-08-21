import sqlite3
import json
import os
import time
import math
from typing import Dict, Any, List, Optional, Tuple

class BitemporalKnowledgeGraph:
    def __init__(self, db_path: str = "/tmp/antigravity_kg.db", shm_cache_path: str = "/dev/shm/kg_warm_cache.json", decay_d: float = 0.5):
        self.db_path = db_path
        self.shm_cache_path = shm_cache_path
        self.decay_d = decay_d
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    properties_json TEXT NOT NULL,
                    created_tx_time REAL NOT NULL,
                    valid_time REAL NOT NULL,
                    access_timestamps_json TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    rel_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    valid_time REAL NOT NULL,
                    tx_time REAL NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES entities(entity_id),
                    FOREIGN KEY(target_id) REFERENCES entities(entity_id)
                );
            """)
            conn.commit()

    def record_entity(self, entity_id: str, entity_type: str, properties: Dict[str, Any], valid_time: Optional[float] = None) -> None:
        now = time.time()
        v_time = valid_time if valid_time is not None else now
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT access_timestamps_json FROM entities WHERE entity_id = ?", (entity_id,))
            row = cursor.fetchone()
            if row:
                access_history = json.loads(row[0])
                access_history.append(now)
                cursor.execute("""
                    UPDATE entities SET properties_json = ?, valid_time = ?, access_timestamps_json = ?
                    WHERE entity_id = ?
                """, (json.dumps(properties), v_time, json.dumps(access_history), entity_id))
            else:
                access_history = [now]
                cursor.execute("""
                    INSERT INTO entities (entity_id, entity_type, properties_json, created_tx_time, valid_time, access_timestamps_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (entity_id, entity_type, json.dumps(properties), now, v_time, json.dumps(access_history)))
            conn.commit()
        self.sync_warm_shm_cache()

    def record_relation(self, source_id: str, relation: str, target_id: str, confidence: float = 1.0, valid_time: Optional[float] = None) -> None:
        now = time.time()
        v_time = valid_time if valid_time is not None else now
        rel_id = f"{source_id}:{relation}:{target_id}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO relations (rel_id, source_id, relation, target_id, confidence, valid_time, tx_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (rel_id, source_id, relation, target_id, confidence, v_time, now))
            conn.commit()

    def compute_act_r_activation(self, access_timestamps: List[float], current_time: Optional[float] = None) -> float:
        now = current_time if current_time is not None else time.time()
        if not access_timestamps:
            return -10.0
        total = 0.0
        for t_k in access_timestamps:
            delta_t = max(now - t_k, 0.001)
            total += delta_t ** (-self.decay_d)
        return math.log(total)

    def get_entity_neighbors(self, entity_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT relation, target_id, confidence FROM relations WHERE source_id = ?
                UNION
                SELECT relation || '_rev', source_id, confidence FROM relations WHERE target_id = ?
            """, (entity_id, entity_id))
            rows = cursor.fetchall()
            return [{"relation": r[0], "neighbor_id": r[1], "confidence": r[2]} for r in rows]

    def sync_warm_shm_cache(self) -> None:
        now = time.time()
        warm_dict = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT entity_id, entity_type, properties_json, access_timestamps_json FROM entities")
            for row in cursor.fetchall():
                e_id, e_type, props_str, access_str = row
                access_history = json.loads(access_str)
                activation = self.compute_act_r_activation(access_history, now)
                warm_dict[e_id] = {
                    "type": e_type,
                    "properties": json.loads(props_str),
                    "activation": activation,
                    "last_accessed": access_history[-1] if access_history else 0
                }
        try:
            tmp_path = self.shm_cache_path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(warm_dict, f)
            os.replace(tmp_path, self.shm_cache_path)
        except Exception:
            pass

    def fast_shm_lookup(self, entity_id: str) -> Optional[Dict[str, Any]]:
        if os.path.exists(self.shm_cache_path):
            try:
                with open(self.shm_cache_path, "r") as f:
                    cache = json.load(f)
                    return cache.get(entity_id)
            except Exception:
                pass
        return None
