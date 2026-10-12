#!/usr/bin/env python3
"""
6-Field BM25F + Hybrid Graph-RAG Polyphonic Retrieval Engine v2.0 (Clean-Room Edition).
Combines:
1. 6-Field Weighted BM25F (title=3.5, type/tags=2.5, heading=2.0, description=1.8, body=1.0)
2. Hybrid Graph-RAG Supporting-Context Reranker (>= 0.85 cosine entity disambiguation, FORESIGHT-2)
3. SHA-256 Boilerplate Suppression & 1-Based #L1-L<N> Line-Numbered Chunk Headers
4. Weighted Reciprocal Rank Fusion (RRF k=60) + MaxPerDoc=2 MMR Diversity Cap
5. Document Outline Facet Discovery (extract_document_outline)
"""

import re
import math
import hashlib
from collections import Counter
from typing import List, Dict, Any, Optional

FIELD_WEIGHTS = {
    "title": 3.5,
    "type": 2.5,
    "tags": 2.5,
    "heading": 2.0,
    "description": 1.8,
    "body": 1.0,
}


def _tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9_]+", (text or "").lower()) if len(t) >= 2]


def _cosine_similarity_tokens(a_tokens: List[str], b_tokens: List[str]) -> float:
    if not a_tokens or not b_tokens:
        return 0.0
    ca, cb = Counter(a_tokens), Counter(b_tokens)
    common = set(ca.keys()) & set(cb.keys())
    num = sum(ca[k] * cb[k] for k in common)
    den = math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values()))
    return (num / den) if den > 0 else 0.0


def format_line_numbered_chunk(doc_id: str, text: str, start_line: int = 1) -> str:
    """Formats a chunk with a 1-based #L<start>-L<end> header."""
    lines = (text or "").splitlines() or [""]
    end_line = start_line + len(lines) - 1
    numbered = [f"{start_line + idx}: {ln}" for idx, ln in enumerate(lines)]
    return f"[{doc_id}#L{start_line}-L{end_line}]\n" + "\n".join(numbered)


def extract_document_outline(doc_id: str, markdown_text: str) -> List[Dict[str, Any]]:
    """Extracts H1-H3 structural outline headings with 1-based line ranges."""
    lines = (markdown_text or "").splitlines()
    headings = []
    for idx, line in enumerate(lines, start=1):
        m = re.match(r"^(#{1,3})\s+(.+)$", line.strip())
        if m:
            headings.append({"doc_id": doc_id, "level": len(m.group(1)), "title": m.group(2).strip(), "start_line": idx})
    for i, h in enumerate(headings):
        h["end_line"] = (headings[i + 1]["start_line"] - 1) if (i + 1 < len(headings)) else len(lines)
    return headings


class PolyphonicRetriever:
    def __init__(self, rrf_k: int = 60, max_per_doc: int = 2, entity_sim_threshold: float = 0.85):
        self.rrf_k = rrf_k
        self.max_per_doc = max_per_doc
        self.entity_sim_threshold = entity_sim_threshold

    def deduplicate_boilerplate(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen_hashes = set()
        unique_docs = []
        for d in docs:
            body_norm = re.sub(r"\s+", " ", str(d.get("body") or d.get("text") or "").strip().lower())
            h = hashlib.sha256(body_norm.encode("utf-8")).hexdigest()
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_docs.append(d)
        return unique_docs

    def score_bm25f_6field(self, query: str, docs: List[Dict[str, Any]], k1: float = 1.2, b: float = 0.75) -> List[Dict[str, Any]]:
        q_tokens = _tokenize(query)
        if not q_tokens or not docs:
            return docs
        n_docs = len(docs)
        df: Counter = Counter()
        doc_field_tokens: List[Dict[str, List[str]]] = []

        for d in docs:
            ftoks = {
                "title": _tokenize(str(d.get("title", ""))),
                "type": _tokenize(str(d.get("type", ""))),
                "tags": _tokenize(" ".join(d.get("tags", [])) if isinstance(d.get("tags"), list) else str(d.get("tags", ""))),
                "heading": _tokenize(str(d.get("heading", ""))),
                "description": _tokenize(str(d.get("description", ""))),
                "body": _tokenize(str(d.get("body") or d.get("text") or "")),
            }
            doc_field_tokens.append(ftoks)
            all_t = set(t for tl in ftoks.values() for t in tl)
            for t in all_t:
                df[t] += 1

        avg_len = max(1.0, sum(len(ft["body"]) for ft in doc_field_tokens) / n_docs)
        scored = []
        for d, ftoks in zip(docs, doc_field_tokens):
            score = 0.0
            body_len = max(1, len(ftoks["body"]))
            for qt in q_tokens:
                idf = math.log(1.0 + (n_docs - df[qt] + 0.5) / (df[qt] + 0.5))
                weighted_tf = 0.0
                for fname, weight in FIELD_WEIGHTS.items():
                    tf = ftoks[fname].count(qt)
                    weighted_tf += weight * tf
                norm_tf = (weighted_tf * (k1 + 1.0)) / (weighted_tf + k1 * (1.0 - b + b * (body_len / avg_len)))
                score += idf * norm_tf
            item = dict(d)
            item["bm25f_score"] = round(score, 4)
            scored.append(item)
        return sorted(scored, key=lambda x: x["bm25f_score"], reverse=True)

    def rerank_with_graph_rag(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        kg_entities: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        FORESIGHT-2 Hybrid Graph-RAG Supporting-Context Reranker:
        Disambiguates polysemous entities using >= 0.85 cosine similarity against KG context
        and boosts candidates connected to active KG entities.
        """
        q_toks = _tokenize(query)
        kg_entities = kg_entities or []
        reranked = []
        for idx, cand in enumerate(candidates):
            c_toks = _tokenize(str(cand.get("title", "")) + " " + str(cand.get("body") or cand.get("text") or ""))
            base_rrf = 1.0 / (self.rrf_k + idx + 1)
            bm25 = float(cand.get("bm25f_score", 0.0))
            graph_boost = 0.0
            for ent in kg_entities:
                e_toks = _tokenize(str(ent.get("label", "")) + " " + str(ent.get("description", "")))
                sim = _cosine_similarity_tokens(c_toks, e_toks)
                if sim >= self.entity_sim_threshold or str(ent.get("id", "")) in str(cand.get("entities", [])):
                    graph_boost += 0.35
            item = dict(cand)
            item["hybrid_score"] = round(bm25 + (base_rrf * 10.0) + graph_boost, 4)
            reranked.append(item)
        reranked.sort(key=lambda x: x["hybrid_score"], reverse=True)

        # Enforce MaxPerDoc diversity cap
        doc_counts: Counter = Counter()
        final_list = []
        for item in reranked:
            parent_doc = str(item.get("doc_id") or item.get("id") or "")
            if doc_counts[parent_doc] < self.max_per_doc:
                doc_counts[parent_doc] += 1
                final_list.append(item)
        return final_list

    def retrieve(
        self,
        query: str,
        corpus: List[Dict[str, Any]],
        kg_entities: Optional[List[Dict[str, Any]]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        deduped = self.deduplicate_boilerplate(corpus)
        bm25_ranked = self.score_bm25f_6field(query, deduped)
        reranked = self.rerank_with_graph_rag(query, bm25_ranked, kg_entities=kg_entities)
        return reranked[:top_k]
