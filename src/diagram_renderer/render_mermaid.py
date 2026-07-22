#!/usr/bin/env python3
"""
Offline Diagram Renderer for Antigravity Web Hub.
Compiles Mermaid flowcharts, sequence diagrams, and architecture diagrams into high-resolution PNG/SVG images.
"""

import os
import sys
import subprocess
import tempfile
import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [DIAGRAM-RENDERER] %(message)s")

def render_mermaid_to_png(mermaid_code: str, output_path: str) -> str:
    """Compiles a raw Mermaid code block into a PNG image file."""
    output_path = os.path.abspath(os.path.expanduser(output_path))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".mmd", mode="w", encoding="utf-8", delete=False) as f:
        f.write(mermaid_code.strip())
        mmd_path = f.name

    try:
        # 1. Try mmdc (Mermaid CLI) if available
        cmd = ["npx", "-y", "@mermaid-js/mermaid-cli", "-i", mmd_path, "-o", output_path, "-b", "transparent"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and os.path.exists(output_path):
            logging.info(f"Successfully compiled diagram to {output_path} via mmdc.")
            return output_path
    except Exception as e:
        logging.warning(f"mmdc execution failed or timed out: {e}")
    finally:
        if os.path.exists(mmd_path):
            os.remove(mmd_path)

    # 2. Fallback: Generate self-contained SVG/HTML diagram wrapper
    svg_fallback_path = output_path if output_path.endswith(".svg") else output_path + ".svg"
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400" viewBox="0 0 800 400">
  <rect width="100%" height="100%" fill="#1e1e2e" rx="10"/>
  <text x="50%" y="30" fill="#cdd6f4" font-family="sans-serif" font-size="18" font-weight="bold" text-anchor="middle">Mermaid Architecture Diagram</text>
  <foreignObject x="20" y="60" width="760" height="320">
    <pre xmlns="http://www.w3.org/1999/xhtml" style="color: #a6adc8; font-family: monospace; font-size: 13px; white-space: pre-wrap;">{mermaid_code.strip()}</pre>
  </foreignObject>
</svg>"""
    with open(svg_fallback_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    logging.info(f"Generated SVG fallback diagram at {svg_fallback_path}")
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
        img_path = os.path.join(output_dir, f"diagram_{count}.png")
        render_mermaid_to_png(code, img_path)
        return f"![Architecture Diagram {count}]({img_path})"

    return pattern.sub(replacer, markdown_text)

if __name__ == "__main__":
    sample = "flowchart TD\n  Client[Web Browser] -->|HTTPS| LB[Load Balancer]\n  LB --> VM[N4 VM]"
    out = "/tmp/test_diagram.svg"
    render_mermaid_to_png(sample, out)
    print(f"Sample diagram rendered to: {out}")
