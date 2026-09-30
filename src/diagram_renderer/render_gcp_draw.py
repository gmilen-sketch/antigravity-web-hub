#!/usr/bin/env python3
"""
GCP Draw DSL & BENTO Architecture Renderer (`render_gcp_draw.py` v15.2 — Clean-Room Edition).
Compiles declarative `.gcpdraw` topology specifications into BENTO-styled SVG/PNG architecture diagrams.
"""
import argparse
import os
import re
from typing import List, Tuple

BENTO_PALETTE = [
    ("#16233A", "#38BDF8"),
    ("#1E293B", "#34D399"),
    ("#1E1B4B", "#C084FC"),
    ("#172554", "#FBBF24"),
]


def parse_gcp_draw_nodes(dsl_text: str) -> List[Tuple[str, str]]:
    nodes: List[Tuple[str, str]] = []
    for line in dsl_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("meta") or s.startswith("paths") or s in ("{", "}"):
            continue
        m = re.match(r'^([a-zA-Z0-9_.-]+)\s+([a-zA-Z0-9_.-]+)(?:\s+"([^"]+)")?', s)
        if m and m.group(1) not in ("title", "direction", "card", "group", "gcp"):
            ntype, nid, label = m.group(1), m.group(2), m.group(3) or m.group(2)
            nodes.append((ntype, label))
    if not nodes:
        nodes = [("compute", "Client Tier"), ("iap", "Zero-Trust Proxy"), ("vertex_ai", "Model Router")]
    return nodes[:8]


def render_gcp_draw_to_svg(dsl_text: str, output_path: str, width: int = 1280) -> str:
    output_path = os.path.abspath(os.path.expanduser(output_path))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    nodes = parse_gcp_draw_nodes(dsl_text)
    card_w = min(240, max(140, (width - 80) // max(len(nodes), 1) - 24))
    svg_boxes = []
    for idx, (ntype, label) in enumerate(nodes):
        fill, stroke = BENTO_PALETTE[idx % len(BENTO_PALETTE)]
        x = 40 + idx * (card_w + 24)
        y = 90
        svg_boxes.append(
            f'<g transform="translate({x},{y})">'
            f'<rect width="{card_w}" height="120" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
            f'<text x="{card_w//2}" y="45" fill="{stroke}" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">{ntype.upper()}</text>'
            f'<text x="{card_w//2}" y="78" fill="#F8FAFC" font-family="sans-serif" font-size="14" font-weight="bold" text-anchor="middle">{label[:22]}</text>'
            f'</g>'
        )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="280" viewBox="0 0 {width} 280">
  <rect width="100%" height="100%" fill="#0F172A" rx="14"/>
  <text x="40" y="42" fill="#F8FAFC" font-family="sans-serif" font-size="20" font-weight="bold">Google Cloud Architecture Topology (BENTO v15.2)</text>
  {"".join(svg_boxes)}
</svg>"""
    svg_path = output_path if output_path.endswith(".svg") else output_path + ".svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return svg_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render GCP Draw DSL to BENTO SVG")
    parser.add_argument("-i", "--input", type=str, default=None)
    parser.add_argument("-o", "--output", type=str, default="/tmp/gcp-architecture.svg")
    args = parser.parse_args()
    dsl = open(args.input, encoding="utf-8").read() if args.input and os.path.exists(args.input) else ""
    out = render_gcp_draw_to_svg(dsl, args.output)
    print(f"Rendered GCP Draw diagram to {out}")
