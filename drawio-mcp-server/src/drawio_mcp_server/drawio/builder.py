"""Serialize a Diagram back into uncompressed *.drawio XML.

The output is intentionally readable so it diffs cleanly in git. draw.io
reads it natively as long as "Compressed" is left unchecked when the user
later re-saves from the desktop / extension UI.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape, quoteattr

from ..types import Diagram
from .shapes import DEFAULT_EDGE_STYLE, SHAPE_STYLES


def build_drawio(diagram: Diagram) -> str:
    cells: list[str] = [
        '        <mxCell id="0" />',
        '        <mxCell id="1" parent="0" />',
    ]

    for node in diagram.nodes:
        if node.raw_style:
            style = node.raw_style
        else:
            style = _merge_style(SHAPE_STYLES[node.shape], node.style)
        parent = node.parent_id or "1"
        cells.append(
            f'        <mxCell id={quoteattr(node.id)} value={quoteattr(node.label)}\n'
            f'          style={quoteattr(style)} vertex="1" parent={quoteattr(parent)}>\n'
            f'          <mxGeometry x="{node.x}" y="{node.y}" '
            f'width="{node.width}" height="{node.height}" as="geometry" />\n'
            f"        </mxCell>"
        )

    for edge in diagram.edges:
        style = _merge_style(DEFAULT_EDGE_STYLE, edge.style)

        # Render the step number directly INTO the edge label as a
        # prefix ("1. uploads", "2. logs", ...). This puts the number
        # above the connector in the same white-pill that the label
        # itself uses, so it renders identically in every drawio
        # variant (desktop, web, VS Code extension). The user can
        # later reference these numbers when adding descriptions /
        # details to the architecture write-up.
        if edge.step_index is not None and edge.step_index > 0:
            visible_label = (
                f"{edge.step_index}. {edge.label}" if edge.label else str(edge.step_index)
            )
        else:
            visible_label = edge.label or ""

        # Build the mxGeometry payload. Two things can live inside it:
        # 1. an `mxPoint as="offset"` that physically lifts the label
        #    22px above the connector line (only when there's a label
        #    — `verticalAlign=bottom` is honored by drawio desktop but
        #    ignored by some webview renderers; the offset point is
        #    the cross-renderer guarantee). 22px (was 14px) keeps the
        #    label clearly above the arrow shaft with room for an icon
        #    label sitting underneath the icon above the edge.
        # 2. an `<Array as="points">` of explicit routing waypoints
        #    that force drawio's orthogonal router through known-empty
        #    row-gap corridors (only when add_edge computed them for a
        #    cross-container edge).
        geom_inner: list[str] = []
        if visible_label:
            geom_inner.append('            <mxPoint x="0" y="-22" as="offset" />')
        if edge.waypoints:
            pts = "\n".join(
                f'              <mxPoint x="{x}" y="{y}" />'
                for (x, y) in edge.waypoints
            )
            geom_inner.append(
                '            <Array as="points">\n'
                + pts
                + "\n            </Array>"
            )
        if geom_inner:
            geometry = (
                '          <mxGeometry relative="1" as="geometry">\n'
                + "\n".join(geom_inner)
                + "\n          </mxGeometry>"
            )
        else:
            geometry = '          <mxGeometry relative="1" as="geometry" />'
        cells.append(
            f'        <mxCell id={quoteattr(edge.id)} value={quoteattr(visible_label)}\n'
            f'          style={quoteattr(style)} edge="1" parent="1"\n'
            f"          source={quoteattr(edge.source_id)} target={quoteattr(edge.target_id)}>\n"
            f"{geometry}\n"
            f"        </mxCell>"
        )

    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    diagram_id = _slug(diagram.name)
    return "\n".join(
        [
            f'<mxfile host="drawio-mcp-server" modified="{modified}" '
            f'agent="drawio-mcp-server/0.1" version="24.0.0">',
            f"  <diagram name={quoteattr(diagram.name)} id={quoteattr(diagram_id)}>",
            '    <mxGraphModel dx="1422" dy="757" grid="1" gridSize="10" guides="1" '
            'tooltips="1" connect="1"',
            '      arrows="1" fold="1" page="1" pageScale="1" pageWidth="1500" '
            'pageHeight="900" math="0" shadow="0">',
            "      <root>",
            "\n".join(cells),
            "      </root>",
            "    </mxGraphModel>",
            "  </diagram>",
            "</mxfile>",
            "",
        ]
    )


def _merge_style(base: str, extra: dict[str, str] | None) -> str:
    if not extra:
        return base
    return base + "".join(f"{k}={v};" for k, v in extra.items())


def _slug(s: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return out or "diagram"


# Re-export escape so callers do not have to import xml.sax.saxutils directly.
__all__ = ["build_drawio", "escape"]
