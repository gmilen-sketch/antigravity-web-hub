import math
import re
from typing import Dict, Any, List, Optional, Tuple, Set

class PolyphonicRetriever:
    def __init__(self, kg_instance, rrf_k: int = 60, mmr_lambda: float = 0.70):
        self.kg = kg_instance
        self.rrf_k = rrf_k
        self.mmr_lambda = mmr_lambda

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())

    def _score_bm25(self, query: str, documents: List[Tuple[str, str]]) -> Dict[str, float]:
        q_tokens = self._tokenize(query)
        scores = {}
        doc_tokens = {doc_id: self._tokenize(text) for doc_id, text in documents}
        avg_len = sum(len(toks) for toks in doc_tokens.values()) / max(len(doc_tokens), 1)
        k1 = 1.5
        b = 0.75

        # Compute IDF
        idf = {}
        num_docs = len(documents)
        for qt in set(q_tokens):
            df = sum(1 for toks in doc_tokens.values() if qt in toks)
            idf[qt] = math.log(1 + (num_docs - df + 0.5) / (df + 0.5))

        for doc_id, toks in doc_tokens.items():
            doc_len = len(toks)
            score = 0.0
            for qt in q_tokens:
                if qt in toks:
                    tf = toks.count(qt)
                    num = tf * (k1 + 1)
                    denom = tf + k1 * (1 - b + b * (doc_len / avg_len))
                    score += idf[qt] * (num / denom)
            scores[doc_id] = score
        return scores

    def search_polyphonic(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        # Fetch entities from KG
        entities = []
        import sqlite3, json
        with sqlite3.connect(self.kg.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT entity_id, entity_type, properties_json, access_timestamps_json FROM entities")
            for row in cursor.fetchall():
                e_id, e_type, props_str, access_str = row
                props = json.loads(props_str)
                text = f"{e_id} {e_type} {json.dumps(props)}"
                entities.append({
                    "id": e_id,
                    "type": e_type,
                    "props": props,
                    "text": text,
                    "access": json.loads(access_str)
                })

        if not entities:
            return []

        doc_tuples = [(e["id"], e["text"]) for e in entities]
        bm25_scores = self._score_bm25(query, doc_tuples)

        # Build Graph Degree Map & Distances
        degrees = {}
        with sqlite3.connect(self.kg.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT source_id, COUNT(*) FROM relations GROUP BY source_id
                UNION ALL
                SELECT target_id, COUNT(*) FROM relations GROUP BY target_id
            """)
            for row in cursor.fetchall():
                node_id, cnt = row
                degrees[node_id] = degrees.get(node_id, 0) + cnt

        # Epistemic Trust Table
        TRUST_TIERS = {
            "Rule": 1.00,
            "Invariant": 1.00,
            "Tenant": 0.90,
            "Service": 0.85,
            "Database": 0.85,
            "Inference": 0.50
        }

        # 4 Voices Ranking
        # Voice 1: Lexical BM25
        ranked_v1 = sorted(entities, key=lambda e: bm25_scores.get(e["id"], 0.0), reverse=True)
        # Voice 2: Graph Authority
        ranked_v2 = sorted(entities, key=lambda e: degrees.get(e["id"], 0), reverse=True)
        # Voice 3: Epistemic Veracity
        ranked_v3 = sorted(entities, key=lambda e: TRUST_TIERS.get(e["type"], 0.70), reverse=True)
        # Voice 4: ACT-R Freshness
        ranked_v4 = sorted(entities, key=lambda e: self.kg.compute_act_r_activation(e["access"]), reverse=True)

        # Reciprocal Rank Fusion (RRF)
        rrf_scores = {}
        for voice_list in [ranked_v1, ranked_v2, ranked_v3, ranked_v4]:
            for rank, entity in enumerate(voice_list, 1):
                e_id = entity["id"]
                rrf_scores[e_id] = rrf_scores.get(e_id, 0.0) + (1.0 / (self.rrf_k + rank))

        # Graph-Aware MMR Reranking
        selected_ids: List[str] = []
        selected_entities: List[Dict[str, Any]] = []
        candidate_pool = list(entities)

        while len(selected_entities) < min(top_k, len(entities)):
            best_e = None
            best_mmr = -float("inf")

            for cand in candidate_pool:
                cand_id = cand["id"]
                rel_score = rrf_scores.get(cand_id, 0.0)

                # Compute topological redundancy against already selected
                max_redundancy = 0.0
                for sel_id in selected_ids:
                    # Check graph distance
                    neighbors = [n["neighbor_id"] for n in self.kg.get_entity_neighbors(sel_id)]
                    is_1_hop = cand_id in neighbors or cand_id == sel_id
                    
                    if is_1_hop:
                        phi_g = 0.0 # 0 penalty for 1-hop causal chain
                    else:
                        phi_g = 1.0 # Standard diversity elimination
                    
                    # Lexical similarity
                    sim = 1.0 if cand_id == sel_id else 0.5
                    redundancy = phi_g * sim
                    if redundancy > max_redundancy:
                        max_redundancy = redundancy

                mmr_score = self.mmr_lambda * rel_score - (1.0 - self.mmr_lambda) * max_redundancy
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_e = cand

            if best_e:
                selected_ids.append(best_e["id"])
                selected_entities.append(best_e)
                candidate_pool.remove(best_e)
            else:
                break

        return selected_entities
