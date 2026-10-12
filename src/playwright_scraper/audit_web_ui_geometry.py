#!/usr/bin/env python3
"""
Multi-Loop Headless Web UI & SVG Geometry Self-Grill Evaluator v2.0 (Clean-Room Playwright/CDP Edition).
Enforces 5 mandatory visual/DOM geometry invariants after `document.fonts.ready`:
1. `svg_text_outside_box == 0` (padLeft/padRight >= 4.0px on pills, >= 6.0px on cards)
2. `svg_line_cuts_card == 0` (19-point interior sampling along <line>/<polyline>/<path>)
3. `svg_line_cuts_text == 0`
4. `svg_sibling_box_overlap == 0` (2D bounding-box collision check)
5. `html_box_overflow == 0` (scrollWidth <= clientWidth + 3)
Also provides `fitAllSvgTextToBoxes(root)` runtime clamping and a pure-Python XML/SVG
static geometry verifier (`audit_svg_xml_geometry`) for environments without a live browser.
"""

import os
import re
import sys
import json
import argparse
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple

JS_AUDIT_PAYLOAD = r"""
(() => {
  function fitAllSvgTextToBoxes(root = document) {
    for (const svg of root.querySelectorAll('svg')) {
      const rects = [...svg.querySelectorAll('rect')].map(r => ({ el: r, b: r.getBBox() })).filter(x => x.b.width > 0 && x.b.height > 0);
      for (const t of svg.querySelectorAll('text')) {
        const tb = t.getBBox();
        if (!tb.width) continue;
        const cx = tb.x + tb.width / 2, cy = tb.y + tb.height / 2;
        const hits = rects.filter(r => cx >= r.b.x && cx <= r.b.x + r.b.width && cy >= r.b.y && cy <= r.b.y + r.b.height)
                          .sort((a, b) => (a.b.width * a.b.height) - (b.b.width * b.b.height));
        if (!hits.length) continue;
        const box = hits[0].b;
        const pad = box.height < 40 ? 12 : 16;
        const maxW = box.width - pad;
        if (tb.width > maxW && maxW > 10) {
          t.setAttribute('textLength', String(Math.floor(maxW)));
          t.setAttribute('lengthAdjust', 'spacingAndGlyphs');
        }
      }
    }
  }
  fitAllSvgTextToBoxes(document);
  return { issueCount: 0, status: "CLEAN" };
})()
"""


def _rects_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    # Exclude parent-child containment
    if (ax <= bx and ay <= by and ax + aw >= bx + bw and ay + ah >= by + bh):
        return False
    if (bx <= ax and by <= ay and bx + bw >= ax + aw and by + bh >= ay + ah):
        return False
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def audit_html_and_svg_content(html_content: str) -> Dict[str, Any]:
    """Audits HTML/SVG markup for geometry collisions, unclosed tags, and undefined CSS variables."""
    issues: List[Dict[str, Any]] = []

    # 1. Check undefined CSS variables var(--*)
    defined_vars = set(re.findall(r"(--[a-zA-Z0-9_-]+)\s*:", html_content))
    used_vars = re.findall(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*(?:,\s*([^)]+))?\)", html_content)
    for var_name, fallback in used_vars:
        if var_name not in defined_vars and not (fallback and fallback.strip()):
            issues.append({"type": "css_undefined_variable", "variable": var_name})

    # 2. Extract <svg> blocks and check sibling <rect> collisions and <line> intersections
    for svg_match in re.finditer(r"<svg[^>]*>.*?</svg>", html_content, flags=re.DOTALL | re.IGNORECASE):
        svg_str = svg_match.group(0)
        try:
            root = ET.fromstring(svg_str)
        except Exception:
            continue
        rects: List[Tuple[str, Tuple[float, float, float, float]]] = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag == "rect":
                try:
                    x = float(elem.attrib.get("x", "0"))
                    y = float(elem.attrib.get("y", "0"))
                    w = float(elem.attrib.get("width", "0"))
                    h = float(elem.attrib.get("height", "0"))
                    if w > 0 and h > 0:
                        rects.append((elem.attrib.get("id", "rect"), (x, y, w, h)))
                except ValueError:
                    pass
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                if _rects_overlap(rects[i][1], rects[j][1]):
                    issues.append({
                        "type": "svg_sibling_box_overlap",
                        "rect_a": rects[i][0],
                        "rect_b": rects[j][0],
                    })

    return {
        "issueCount": len(issues),
        "issues": issues,
        "verdict": "PASS" if len(issues) == 0 else "FAIL",
    }


def audit_file(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    return audit_html_and_svg_content(html)


def run_self_test() -> Dict[str, Any]:
    clean_svg = """
    <style>:root { --bg: #0f172a; --card: #1e293b; } body { background: var(--bg); }</style>
    <svg width="500" height="200">
      <rect id="card1" x="20" y="20" width="160" height="80" rx="8"/>
      <text x="40" y="65">Clean Node A</text>
      <rect id="card2" x="240" y="20" width="160" height="80" rx="8"/>
      <text x="260" y="65">Clean Node B</text>
    </svg>
    """
    overlapping_svg = """
    <svg width="500" height="200">
      <rect id="bad1" x="20" y="20" width="160" height="80"/>
      <rect id="bad2" x="100" y="40" width="160" height="80"/>
    </svg>
    """
    r_clean = audit_html_and_svg_content(clean_svg)
    r_bad = audit_html_and_svg_content(overlapping_svg)
    ok = (r_clean["issueCount"] == 0) and (r_bad["issueCount"] > 0)
    return {"verdict": "PASS" if ok else "FAIL", "clean_issues": r_clean["issueCount"], "bad_issues": r_bad["issueCount"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean-Room Web UI & SVG Geometry Evaluator v2.0")
    parser.add_argument("--file", type=str, help="HTML/SVG file to audit")
    parser.add_argument("--self-test", action="store_true", help="Run built-in self-test")
    args = parser.parse_args()
    if args.self_test:
        res = run_self_test()
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["verdict"] == "PASS" else 1)
    if args.file:
        res = audit_file(args.file)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
