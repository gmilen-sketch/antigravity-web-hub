#!/usr/bin/env python3
"""
FastMCP Server for Headless Browser Navigation & DOM Scraping in Antigravity Web Hub.
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

from playwright_scraper import fetch_page_markdown

mcp = FastMCP("playwright_scraper_mcp")

@mcp.tool()
def browse_webpage(url: str) -> str:
    """Navigates to a public web page and extracts its content as structured markdown text."""
    return fetch_page_markdown(url)

if __name__ == "__main__":
    mcp.run()
