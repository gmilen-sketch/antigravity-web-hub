#!/usr/bin/env python3
"""
Multi-Hop Personalized PageRank (PPR) Knowledge Graph Traversal Engine (Clean-Room Edition).
Computes Personalized PageRank from seed entities with damping alpha = 0.85.
"""

from typing import Dict, Any, List


def personalized_pagerank(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    seed_ids: List[str],
    damping: float = 0.85,
    iterations: int = 20,
) -> Dict[str, float]:
    node_ids = [str(n.get("id")) for n in nodes if n.get("id")]
    if not node_ids:
        return {}
    adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        u, v = str(e.get("source", "")), str(e.get("target", ""))
        if u in adj and v in adj:
            adj[u].append(v)
            adj[v].append(u)

    valid_seeds = [s for s in seed_ids if s in adj] or node_ids
    teleport = {nid: (1.0 / len(valid_seeds) if nid in valid_seeds else 0.0) for nid in node_ids}
    scores = dict(teleport)

    for _ in range(iterations):
        nxt = {nid: (1.0 - damping) * teleport[nid] for nid in node_ids}
        for u in node_ids:
            nbrs = adj[u]
            if nbrs:
                share = damping * scores[u] / len(nbrs)
                for v in nbrs:
                    nxt[v] += share
            else:
                for v in valid_seeds:
                    nxt[v] += damping * scores[u] / len(valid_seeds)
        scores = nxt

    return {k: round(v, 6) for k, v in sorted(scores.items(), key=lambda item: item[1], reverse=True)}
