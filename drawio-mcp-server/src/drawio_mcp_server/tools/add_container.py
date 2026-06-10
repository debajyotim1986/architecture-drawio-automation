"""Create a labeled swimlane container — the building block for
layered, deck-quality architecture diagrams.

Why this tool exists
--------------------
The default `add_node` workflow drops every component on a 4-column
wrap grid, which renders fine but looks "boxy" and doesn't convey the
architectural structure of the system. A diagram is much more readable
when components are grouped into labeled columns/zones (Ingestion,
Processing, Staging, Curation, Observability, External, ...) — the
visual structure mirrors the data flow.

This tool creates one such labeled column. The create-diagram prompt
calls it 4–6 times up front (one per architectural layer), then calls
`add_node(..., parent_id=<container_id>)` to drop each component
inside the right column. The MCP server handles all the relative
coordinate math; the LLM only has to pick a layer for each node.

Layout
------
- `column_index` (0-based) places the container in a left-to-right
  arrangement. Width defaults to 240px, gap 20px, so column 0 sits at
  x=40, column 1 at x=300, column 2 at x=560, etc.
- Pass explicit `x` / `y` / `width` / `height` for full control.
- Children of the container (added later via
  `add_node(..., parent_id=<this id>)`) auto-stack vertically inside
  with enough room for 64px GCP icons + labels.
"""

from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..drawio.shapes import DEFAULT_SIZE, SHAPE_STYLES, SWIMLANE_COLORS
from ..types import DiagramNode
from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

_SWIMLANE_W, _SWIMLANE_H = DEFAULT_SIZE["swimlane"]
_COLUMN_ORIGIN_X = 40.0
_COLUMN_ORIGIN_Y = 40.0
# Wide gap between swimlanes so the orthogonal edge router has a
# clear horizontal routing lane to use when an edge crosses multiple
# columns. History:
#   20  — original; left edges no choice but to route along the same
#         y as an intermediate-column icon, drawing the arrow ON TOP
#         of the icon.
#   80  — fixed the icon-overlap problem and gave one usable corridor
#         per gap.
#   140 — current. With the busy-node framing pass (`_frame_busy_nodes`
#         in add_edge.py) busy icons now wear a visible card, so the
#         space between cards reads as crowded at 80. 140 px between
#         column edges = 70 px on either side of the corridor centerline,
#         which lets BOTH a connector and its label sit clear of either
#         neighbouring container.
_COLUMN_GAP = 140.0


add_container_tool = Tool(
    name="add_container",
    description=(
        "Create a labeled swimlane (vertical column with a colored header) "
        "that groups related components in an architecture diagram. Call "
        "this 4-6 times at the START of a create-diagram flow — one per "
        "architectural layer (e.g. 'On-Prem Source', 'Ingestion', "
        "'Staging', 'Curation', 'Observability') — BEFORE any `add_node` "
        "call. Then drop components into the right column with "
        "`add_node(label=..., parent_id='<container_id>', gcp_icon=...)`. "
        "Returns the assigned container id; use it as `parent_id` on every "
        "`add_node` call that belongs to this layer."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "diagram": {"type": "string", "description": "Diagram filename."},
            "label": {
                "type": "string",
                "description": (
                    "Header text for the swimlane (the layer name). Keep it "
                    "short — 'Ingestion', 'BigQuery Staging', 'Observability'."
                ),
            },
            "color_hint": {
                "type": "string",
                "enum": list(SWIMLANE_COLORS.keys()),
                "description": (
                    "Picks the header color from a small curated palette. "
                    "Use 'ingestion' (blue), 'processing' (yellow), "
                    "'staging' (green), 'curation' (purple), 'serving' "
                    "(orange), 'observability' (gray), 'external' / "
                    "'security' (red), or 'default'. Choosing intuitive "
                    "colors helps the reader follow data flow at a glance."
                ),
            },
            "column_index": {
                "type": "integer",
                "minimum": 0,
                "description": (
                    "0-based slot in a left-to-right layout. The server "
                    "computes x automatically (origin 40 + index * (width + "
                    "gap)). Ignored when explicit `x` is given."
                ),
            },
            "id": {"type": "string", "description": "Optional stable id; auto-generated if omitted."},
            "x": {"type": "number"},
            "y": {"type": "number"},
            "width": {"type": "number"},
            "height": {"type": "number"},
        },
        "required": ["diagram", "label"],
        "additionalProperties": False,
    },
)


async def add_container(args: dict[str, Any], cfg: ServerConfig) -> dict[str, str]:
    diagram_name = str(args.get("diagram") or "")
    label = str(args.get("label") or "")
    if not diagram_name or not label:
        raise ValueError("`diagram` and `label` are required.")

    store = DiagramStore(cfg.diagrams_dir)
    diagram = store.load(diagram_name)

    container_id = str(args.get("id") or _next_id([n.id for n in diagram.nodes], "g"))

    color_hint = str(args.get("color_hint") or "default")
    header_fill, stroke = SWIMLANE_COLORS.get(color_hint, SWIMLANE_COLORS["default"])
    # Start from the base swimlane style, swap in the palette colors.
    base_style = SHAPE_STYLES["swimlane"]
    style = (
        base_style.replace("fillColor=#dae8fc", f"fillColor={header_fill}")
        .replace("strokeColor=#6c8ebf", f"strokeColor={stroke}")
    )

    width = _num_or(args.get("width"), _SWIMLANE_W)
    height = _num_or(args.get("height"), _SWIMLANE_H)

    if args.get("x") is not None:
        x = _num_or(args.get("x"), _COLUMN_ORIGIN_X)
    else:
        col = int(args.get("column_index") or _next_column_index(diagram.nodes))
        x = _COLUMN_ORIGIN_X + col * (width + _COLUMN_GAP)
    y = _num_or(args.get("y"), _COLUMN_ORIGIN_Y)

    diagram.nodes.append(
        DiagramNode(
            id=container_id,
            label=label,
            shape="swimlane",
            x=x,
            y=y,
            width=width,
            height=height,
            raw_style=style,
        )
    )

    return {
        "id": container_id,
        "path": store.save(diagram_name, diagram),
        "color_hint": color_hint,
    }


def _num_or(v: Any, fallback: float) -> float:
    try:
        return float(v) if v is not None else fallback
    except (TypeError, ValueError):
        return fallback


def _next_id(existing: list[str], prefix: str) -> str:
    taken = set(existing)
    i = 1
    while f"{prefix}{i}" in taken:
        i += 1
    return f"{prefix}{i}"


def _next_column_index(nodes: list[DiagramNode]) -> int:
    """Count existing swimlanes — the next column slot is len()."""
    return sum(1 for n in nodes if n.shape == "swimlane")
