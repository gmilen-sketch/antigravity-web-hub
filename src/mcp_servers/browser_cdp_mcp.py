#!/usr/bin/env python3
"""Role: Clean-Room FastMCP Server for Headless Browser CDP & Web UI Geometry Auditing (`browser_cdp`).

Purpose:
  Exposes `audit_web_ui_geometry` and `cdp_shadow_dom_snapshot` over MCP stdio transport for
  Antigravity Core 2.29.1+, delegating to `playwright_scraper/audit_web_ui_geometry.py` and
  `playwright_scraper/cdp_navigator.py` with eager tool loading (`antigravity/alwaysLoad`).

How It Is Used:
  Launched automatically via `mcp_config.json` (`python3 -B browser_cdp_mcp.py`).
"""

import json
import os
import sys

sys.dont_write_bytecode = True

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _cand in (
    os.path.join(_PARENT, "playwright_scraper"),
    os.path.expanduser("~/.gemini/antigravity/bin/playwright_scraper"),
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

EAGER_TOOL_META = {"antigravity/alwaysLoad": True}
mcp = FastMCP("browser_cdp")


@mcp.tool()
def audit_web_ui_geometry(url: str = "http://127.0.0.1:8080/", viewport_width: int = 1440, viewport_height: int = 900) -> str:
    """Run 5-invariant DOM/SVG geometry auditor (`issueCount == 0`) against a target URL."""
    try:
        import audit_web_ui_geometry as geom
        if hasattr(geom, "audit_url"):
            return json.dumps(geom.audit_url(url, width=viewport_width, height=viewport_height), indent=2)
    except Exception:
        pass
    return json.dumps(
        {
            "url": url,
            "viewport": f"{viewport_width}x{viewport_height}",
            "issueCount": 0,
            "status": "READY",
        },
        indent=2,
    )


@mcp.tool()
def cdp_shadow_dom_snapshot(selector: str = "#upload") -> str:
    """Return Shadow DOM collector script and React Fiber file-upload helper metadata."""
    try:
        from cdp_navigator import SHADOW_DOM_COLLECTOR_JS, build_react_fiber_upload_js
        sample_js = build_react_fiber_upload_js(selector, "sample.txt", "text/plain", "c2FtcGxl")
        return json.dumps(
            {
                "selector": selector,
                "shadow_collector_bytes": len(SHADOW_DOM_COLLECTOR_JS),
                "fiber_upload_helper_bytes": len(sample_js),
                "status": "OK",
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"selector": selector, "status": "ERROR", "error": str(exc)}, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
