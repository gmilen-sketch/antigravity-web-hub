#!/usr/bin/env python3
"""Role: Clean-Room FastMCP Server for 3-Tab AGENT-SSOT-v1 Docs, Cloudstyle Slides & 3-Row Sheet Diffs (`workspace_docs`).

Purpose:
  Exposes `build_agent_ssot_v1_tab3`, `build_cloudstyle_4card_slide`, and `build_3row_sheet_staging_diff`
  over MCP stdio transport, delegating directly to `mcp_google_workspace/agent_ssot_formatter.py`.

How It Is Used:
  Launched automatically via `mcp_config.json` (`python3 -B workspace_docs_mcp.py`).
"""

import json
import os
import sys

sys.dont_write_bytecode = True

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _cand in (
    os.path.join(_PARENT, "mcp_google_workspace"),
    os.path.expanduser("~/.gemini/antigravity/bin/mcp_google_workspace"),
):
    if os.path.isdir(_cand) and _cand not in sys.path:
        sys.path.insert(0, _cand)

try:
    from fastmcp import FastMCP
except ImportError:
    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, name: str = "", **kwargs):
            self.name = name

        def tool(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        def run(self, *args, **kwargs):
            pass

from agent_ssot_formatter import (
    build_3row_sheet_staging_diff as _diff_helper,
    build_agent_ssot_v1_tab3_markdown as _ssot_helper,
    build_cloudstyle_4card_slide_requests as _slide_helper,
)

EAGER_TOOL_META = {"antigravity/alwaysLoad": True}
mcp = FastMCP("workspace_docs")


@mcp.tool()
def build_agent_ssot_v1_tab3(doc_title: str, sections_json: str = "[]") -> str:
    """Generate 3-Tab Inverted-Pyramid AGENT-SSOT-v1 Tab 3 pointer index markdown."""
    try:
        sections = json.loads(sections_json) if sections_json else []
    except Exception:
        sections = []
    if not isinstance(sections, list) or not sections:
        sections = [{"id": "sec-1", "title": "Executive Summary", "lines": "L1-L25"}]
    return _ssot_helper(doc_title, sections)


@mcp.tool()
def build_cloudstyle_4card_slide(slide_id: str = "slide_01", cards_json: str = "[]") -> str:
    """Generate 4-card Google Cloudstyle 720x405pt presentation batchUpdate requests."""
    try:
        cards = json.loads(cards_json) if cards_json else []
    except Exception:
        cards = []
    if not isinstance(cards, list) or not cards:
        cards = [{"title": "Pillar 1"}, {"title": "Pillar 2"}, {"title": "Pillar 3"}, {"title": "Pillar 4"}]
    return json.dumps(_slide_helper(slide_id, cards), indent=2)


@mcp.tool()
def build_3row_sheet_staging_diff(baseline_json: str = "{}", planned_json: str = "{}") -> str:
    """Generate 1-Sheet 3-Row Staging Diff (Row 2 Baseline, Row 3 Planned, Row 4 Delta)."""
    try:
        base = json.loads(baseline_json) if baseline_json else {}
        plan = json.loads(planned_json) if planned_json else {}
    except Exception:
        base, plan = {}, {}
    return json.dumps(_diff_helper(base, plan), indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
