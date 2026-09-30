#!/usr/bin/env python3
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastmcp import FastMCP
from aaak_compressor import AAAKCompressor
from graph_memory import BitemporalKnowledgeGraph
from polyphonic_retriever import PolyphonicRetriever
from subagent_hydrator import SubagentContextHydrator
from anti_overfitting_gate import AntiOverfittingGate
from p0_quality_first_engine import P0QualityFirstEngine, run_self_test as run_p0_test
from p1_quality_first_engine import P1QualityFirstEngine, run_self_test as run_p1_test

mcp = FastMCP("autonomy_engine")

kg = BitemporalKnowledgeGraph()
retriever = PolyphonicRetriever(kg)
hydrator = SubagentContextHydrator()
sdt_gate = AntiOverfittingGate()
p0_engine = P0QualityFirstEngine()
p1_engine = P1QualityFirstEngine()


@mcp.tool()
def compress_text(text: str) -> str:
    """3-pass deterministic token compression for tool logs and session transcripts."""
    return AAAKCompressor.compress_text(text)


@mcp.tool()
def query_knowledge_graph(query: str, top_k: int = 5) -> str:
    """4-voice polyphonic factual search across bitemporal property graph."""
    results = retriever.search_polyphonic(query, top_k=top_k)
    return json.dumps(results, indent=2)


@mcp.tool()
def record_fact(entity_id: str, entity_type: str, properties: dict) -> str:
    """Records an entity or relationship into the bitemporal knowledge graph."""
    kg.record_entity(entity_id, entity_type, properties)
    return "Fact recorded successfully."


@mcp.tool()
def hydrate_subagent_envelope(
    role: str, task_description: str, core_payload: str, resource_pointers: list[str] = []
) -> str:
    """Builds a clean 3-pillar XML envelope (<hydrated_context>) with adaptive budget."""
    return hydrator.hydrate_context_envelope(
        role=role,
        task_description=task_description,
        core_payload=core_payload,
        resource_pointers=resource_pointers,
    )


@mcp.tool()
def verify_quality_circuit_breakers() -> str:
    """Executes the P0 (CB-1..CB-7), P1 (P1-CB-1..P1-CB-7), and 8-Mutant Saboteur self-tests."""
    return json.dumps(
        {
            "p0_engine": run_p0_test(),
            "p1_engine": run_p1_test(),
            "saboteur_benchmark": sdt_gate.run_saboteur_benchmark(),
        },
        indent=2,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
