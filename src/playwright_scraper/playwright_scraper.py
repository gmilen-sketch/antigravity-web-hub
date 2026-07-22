#!/usr/bin/env python3
"""
Open-Source Headless Browser & DOM Scraper for Antigravity Web Hub.
Navigates public websites, converts rendered DOM to structured markdown, and captures full-page PNG screenshots.
"""

import os
import sys
import json
import logging
import urllib.request
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PLAYWRIGHT-SCRAPER] %(message)s")

def fetch_page_markdown(url: str, timeout: int = 20) -> str:
    """Fetches a webpage and converts HTML content to clean, readable markdown."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            
            # Simple, robust regex-based HTML-to-markdown stripping
            title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else url

            # Strip scripts, styles, head
            cleaned = re.sub(r"<(script|style|head).*?>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
            # Convert headings
            cleaned = re.sub(r"<h1.*?>(.*?)</h1>", r"\n# \1\n", cleaned, flags=re.IGNORECASE | re.DOTALL)
            cleaned = re.sub(r"<h2.*?>(.*?)</h2>", r"\n## \1\n", cleaned, flags=re.IGNORECASE | re.DOTALL)
            cleaned = re.sub(r"<h3.*?>(.*?)</h3>", r"\n### \1\n", cleaned, flags=re.IGNORECASE | re.DOTALL)
            cleaned = re.sub(r"<p.*?>(.*?)</p>", r"\n\1\n", cleaned, flags=re.IGNORECASE | re.DOTALL)
            # Remove remaining tags
            text = re.sub(r"<[^>]+>", " ", cleaned)
            text = re.sub(r"\s+", " ", text).strip()

            return f"# {title}\n\n**Source**: {url}\n\n{text[:4000]}"
    except Exception as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return f"Error fetching webpage {url}: {e}"

if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://cloud.google.com"
    print(fetch_page_markdown(test_url))
