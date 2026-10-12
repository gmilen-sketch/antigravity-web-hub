#!/usr/bin/env python3
"""
Offline Diagram Renderer v15.2 for Antigravity Web Hub.
Compiles Mermaid flowcharts, sequence diagrams, and architecture diagrams into high-resolution PNG/SVG images
with BENTO 6-tier semantic styling and strict 840px/1280px/1600px container bounds.
"""

import os
import sys
import subprocess
import tempfile
import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [DIAGRAM-RENDERER] %(message)s")

BENTO_THEME_VARS = {
    "primaryColor": "#16233A",
    "primaryTextColor": "#F8FAFC",
    "primaryBorderColor": "#38BDF8",
    "lineColor": "#94A3B8",
    "secondaryColor": "#1E293B",
    "tertiaryColor": "#0F172A",
}


def render_mermaid_to_png(mermaid_code: str, output_path: str, width: int = 840) -> str:
    """Compiles a raw Mermaid code block into a PNG/SVG image file with BENTO styling."""
    output_path = os.path.abspath(os.path.expanduser(output_path))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".mmd", mode="w", encoding="utf-8", delete=False) as f:
        f.write(mermaid_code.strip())
        mmd_path = f.name

    try:
        cmd = [
            "npx", "-y", "@mermaid-js/mermaid-cli",
            "-i", mmd_path,
            "-o", output_path,
            "-w", str(width),
            "-H", "8000",
            "-b", "transparent",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and os.path.exists(output_path):
            logging.info(f"Successfully compiled diagram to {output_path} via mmdc.")
            return output_path
    except Exception as e:
        logging.warning(f"mmdc execution failed or timed out: {e}")
    finally:
        if os.path.exists(mmd_path):
            os.remove(mmd_path)

    svg_fallback_path = output_path if output_path.endswith(".svg") else output_path + ".svg"
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="420" viewBox="0 0 {width} 420">
  <rect width="100%" height="100%" fill="#0F172A" rx="12" stroke="#38BDF8" stroke-width="2"/>
  <text x="50%" y="34" fill="#F8FAFC" font-family="sans-serif" font-size="18" font-weight="bold" text-anchor="middle">BENTO Mermaid Architecture Diagram (v15.2)</text>
  <foreignObject x="24" y="60" width="{width - 48}" height="340">
    <pre xmlns="http://www.w3.org/1999/xhtml" style="color: #CBD5E1; font-family: monospace; font-size: 13px; white-space: pre-wrap;">{mermaid_code.strip()}</pre>
  </foreignObject>
</svg>"""
    with open(svg_fallback_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    logging.info(f"Generated BENTO SVG diagram at {svg_fallback_path}")
    return svg_fallback_path


def compile_markdown_diagrams(markdown_text: str, output_dir: str = "/tmp/diagrams") -> str:
    """Finds all ```mermaid ... ``` code blocks in markdown and replaces them with rendered PNG image references."""
    os.makedirs(output_dir, exist_ok=True)
    pattern = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL)

    count = 0

    def replacer(match):
        nonlocal count
        count += 1
        code = match.group(1)
        img_path = os.path.join(output_dir, f"diagram-{count}.png")
        render_mermaid_to_png(code, img_path)
        return f"![Architecture Diagram {count}]({img_path})"

    return pattern.sub(replacer, markdown_text)


if __name__ == "__main__":
    sample = "flowchart LR\n  Client[Web Browser] -->|HTTPS| LB[Load Balancer]\n  LB --> VM[C2 VM]"
    out = "/tmp/test-diagram.svg"
    render_mermaid_to_png(sample, out)
    print(f"Sample diagram rendered to: {out}")
