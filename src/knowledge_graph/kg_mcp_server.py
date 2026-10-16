#!/usr/bin/env python3
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from fastmcp import FastMCP
except ImportError:
    class FastMCP:
        def __init__(self, name="", **kwargs):
            self.name = name
        def tool(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator
        def run(self, *args, **kwargs):
            pass
from kg_engine import get_kg_engine

EAGER_TOOL_META = {"antigravity/alwaysLoad": True}

mcp = FastMCP("knowledge_graph")

@mcp.tool()
def kg_search_entities(query: str, limit: int = 10) -> str:
    """Search for entities or concepts stored in the long-term knowledge graph memory."""
    engine = get_kg_engine()
    results = engine.search_nodes(query, limit=limit)
    return json.dumps(results, indent=2)

@mcp.tool()
def kg_get_subgraph_context(target_id: str, max_hops: int = 2) -> str:
    """Retrieve an ultra-compact prompt-ready context block for a target entity or concept."""
    engine = get_kg_engine()
    return engine.get_subgraph_context(target_id, max_hops=max_hops)

@mcp.tool()
def kg_upsert_node(node_id: str, label: str, node_type: str = "entity", description: str = "") -> str:
    """Upsert a new entity, insight, or learning into long-term graph memory."""
    engine = get_kg_engine()
    node = engine.upsert_node(node_id, label, node_type, description)
    return f"Successfully saved entity '{label}' ({node_id}) to knowledge graph."

@mcp.tool()
def kg_upsert_edge(source: str, target: str, relation: str = "relates_to", weight: float = 1.0) -> str:
    """Create a directional relationship/edge between two memory nodes."""
    engine = get_kg_engine()
    edge = engine.upsert_edge(source, target, relation, weight)
    return f"Successfully linked '{source}' --({relation})--> '{target}'."

if __name__ == "__main__":
    mcp.run(transport="stdio")
