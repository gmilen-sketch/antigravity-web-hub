#!/usr/bin/env python3
"""
FastMCP Server for Diagram Rendering in Antigravity Web Hub.
Exposes tools for compiling Mermaid text diagrams into PNG/SVG image artifacts.
"""

import os
import sys
import json
import logging

try:
    from fastmcp import FastMCP
except ImportError:
    class FastMCP:
        def __init__(self, name):
            self.name = name
        def tool(self):
            def decorator(f):
                return f
            return decorator
        def run(self):
            print(f"FastMCP server {self.name} initialized.")

from render_mermaid import render_mermaid_to_png, compile_markdown_diagrams

mcp = FastMCP("diagram_renderer_mcp")

@mcp.tool()
def render_diagram(mermaid_code: str, output_path: str = "/tmp/diagram.png") -> str:
    """Compiles a raw Mermaid code block into a PNG or SVG image artifact."""
    result_path = render_mermaid_to_png(mermaid_code, output_path)
    return f"Successfully compiled diagram artifact to: {result_path}"

@mcp.tool()
def process_markdown_diagrams(markdown_content: str, output_dir: str = "/tmp/diagrams") -> str:
    """Scans markdown content for ```mermaid ... ``` code blocks and replaces them with compiled PNG image references."""
    processed = compile_markdown_diagrams(markdown_content, output_dir=output_dir)
    return processed

if __name__ == "__main__":
    mcp.run()
