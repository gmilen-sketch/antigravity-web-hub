#!/usr/bin/env python3
"""
FastMCP Server for Six Thinking Hats Reasoning in Antigravity Web Hub.
"""

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

from six_hats import format_six_hats_prompt

mcp = FastMCP("six_hats_evaluator_mcp")

@mcp.tool()
def evaluate_architecture_six_hats(topic: str, context: str = "") -> str:
    """Generates a comprehensive 360-degree Six Thinking Hats audit template to pressure-test code, API designs, or architectures."""
    return format_six_hats_prompt(topic, context)

if __name__ == "__main__":
    mcp.run()
