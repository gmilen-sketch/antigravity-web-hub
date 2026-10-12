#!/usr/bin/env python3
"""
3-Tab Inverted-Pyramid Document Architecture (Arm E / AGENT-SSOT-v1),
Cloudstyle Slides v1.7 EMU Layout & 1-Sheet 3-Row Diff Formatter (Clean-Room Public API Edition).
Generates standard Google Workspace REST API v1/v4 JSON batchUpdate payloads:
- Google Docs API v1 (`documents.batchUpdate`): 516.0 pt centered tables & 3-Tab AGENT-SSOT-v1 pointer index
- Google Slides API v1 (`presentations.batchUpdate`): 720x405 pt canvas, 4-card row & 3-shape +-45 deg vector chevrons
- Google Sheets API v4 (`spreadsheets.batchUpdate`): 1-Sheet 3-Row Staging Diff (Current, Planned, Delta)
"""

from typing import Dict, Any, List


def build_agent_ssot_v1_tab3_markdown(doc_title: str, sections: List[Dict[str, Any]]) -> str:
    """Builds Tab 3 ('Only for Agents (Read First — Index & Pointers)' AGENT-SSOT-v1) with 4 self-routing beacons."""
    lines = [
        f"# {doc_title} — Tab 3: Only for Agents (Read First — Index & Pointers)",
        "",
        "> **Protocol**: `AGENT-SSOT-v1` | **Beacon 1**: Read this index first before scanning Tab 2.",
        "> **Beacon 2**: Cite canonical section anchors `#sec-<id>`. **Beacon 3**: Verify numeric deltas in Tab 1.",
        "> **Beacon 4**: Zero raw LaTeX tokens; enforce 516.0 pt centered table geometry.",
        "",
        "| Section ID | Heading Title | Tab 2 Line Range | Primary Key Entities |",
        "| :--- | :--- | :---: | :--- |",
    ]
    for idx, sec in enumerate(sections, start=1):
        sid = sec.get("id", f"sec-{idx:02d}")
        title = sec.get("title", f"Section {idx}")
        lrange = sec.get("lines", f"L{idx*20-19}-L{idx*20}")
        ents = ", ".join(sec.get("entities", ["core"]))
        lines.append(f"| `{sid}` | {title} | `{lrange}` | {ents} |")
    return "\n".join(lines)


def build_gdocs_516pt_centered_table_requests(table_start_index: int, num_columns: int) -> List[Dict[str, Any]]:
    """Generates public Google Docs REST v1 batchUpdate requests to center a table at 516.0 pt."""
    col_width = round(516.0 / max(1, num_columns), 2)
    return [
        {
            "updateTableColumnProperties": {
                "tableStartLocation": {"index": table_start_index},
                "columnIndices": list(range(num_columns)),
                "tableColumnProperties": {
                    "widthType": "FIXED_WIDTH",
                    "width": {"magnitude": col_width, "unit": "PT"},
                },
                "fields": "widthType,width",
            }
        }
    ]


def build_cloudstyle_4card_slide_requests(slide_id: str, cards: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Generates public Google Slides REST v1 batchUpdate requests for the 4-card row (W=151.51 pt)
    and 3 zero-text-inset 2-bar +-45 deg vector chevron connectors (W=16.51 pt).
    """
    card_x_pts = [23.23, 197.24, 371.25, 545.26]
    arrow_x_pts = [177.73, 351.74, 525.76]
    cap_colors = [
        {"red": 0.259, "green": 0.522, "blue": 0.957},
        {"red": 0.918, "green": 0.263, "blue": 0.208},
        {"red": 0.984, "green": 0.737, "blue": 0.016},
        {"red": 0.204, "green": 0.659, "blue": 0.325},
    ]
    reqs: List[Dict[str, Any]] = []
    for i in range(min(4, len(cards))):
        reqs.append({
            "createShape": {
                "objectId": f"{slide_id}_card_{i}_body",
                "shapeType": "RECTANGLE",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {"width": {"magnitude": 151.51, "unit": "PT"}, "height": {"magnitude": 220.49, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": card_x_pts[i], "translateY": 94.51, "unit": "PT"},
                },
            }
        })
        reqs.append({
            "createShape": {
                "objectId": f"{slide_id}_card_{i}_cap",
                "shapeType": "ROUND_2_SAME_RECTANGLE",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {"width": {"magnitude": 151.51, "unit": "PT"}, "height": {"magnitude": 13.51, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": card_x_pts[i], "translateY": 81.0, "unit": "PT"},
                },
            }
        })
        reqs.append({" filler_color_hint": cap_colors[i]} if False else {
            "insertText": {"objectId": f"{slide_id}_card_{i}_body", "text": cards[i].get("title", f"Step {i+1}")}
        })
    for idx, ax in enumerate(arrow_x_pts):
        reqs.append({
            "createShape": {
                "objectId": f"{slide_id}_chevron_{idx}",
                "shapeType": "ELLIPSE",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {"width": {"magnitude": 16.51, "unit": "PT"}, "height": {"magnitude": 16.51, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": ax, "translateY": 186.0, "unit": "PT"},
                },
            }
        })
    return reqs


def build_3row_sheet_staging_diff(baseline: Dict[str, Any], planned: Dict[str, Any]) -> Dict[str, Any]:
    """Builds a 1-Sheet 3-Row Staging Diff (Row 2: Current, Row 3: Planned, Row 4: Delta)."""
    keys = sorted(set(baseline.keys()) | set(planned.keys()))
    delta: Dict[str, Any] = {}
    for k in keys:
        bval, pval = baseline.get(k), planned.get(k)
        if isinstance(bval, (int, float)) and isinstance(pval, (int, float)):
            diff = round(pval - bval, 4)
            delta[k] = f"+{diff}" if diff > 0 else str(diff)
        else:
            delta[k] = "UNCHANGED" if bval == pval else f"{bval} -> {pval}"
    return {
        "headers": ["Row Stage"] + keys,
        "row_2_current_baseline": ["Current (Baseline)"] + [baseline.get(k) for k in keys],
        "row_3_planned_target": ["Planned (Target)"] + [planned.get(k) for k in keys],
        "row_4_delta_variance": ["Delta (Variance)"] + [delta[k] for k in keys],
    }
