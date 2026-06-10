"""Add a title banner at the top of a diagram.

Renders the Title: field from the surgical Jira story as a large bold
heading above the swimlanes, with an optional subtitle line below
(e.g. the Jira key + a short tagline). This is what turns a
generated diagram from "anonymous boxes and lines" into a deck slide
that's safe to drop in front of an architecture review without
re-labeling.

Position: top-left at (40, -60) by default — above the swimlanes
which start at y=40. Drawio handles negative coords cleanly.
Width: spans the full row of swimlanes (1540px = 6 columns × 260px
- 20px gap) so the banner reads as a banner, not a label.
"""

from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..drawio.shapes import SUBTITLE_STYLE, TITLE_STYLE
from ..types import DiagramNode
from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

_TITLE_X = 40.0
_TITLE_Y = -60.0
_TITLE_W = 1540.0
_TITLE_H = 40.0
_SUBTITLE_Y_OFFSET = 38.0   # immediately below the title row
_SUBTITLE_H = 24.0


add_title_tool = Tool(
    name="add_title",
    description=(
        "Add a styled title banner above the swimlanes. Call this FIRST in "
        "a create-diagram flow (before any add_container / add_node). The "
        "title text should come from the surgical story's `Title:` line. "
        "An optional subtitle adds a smaller second line (typically the "
        "Jira key + a one-line tagline). The banner has a transparent "
        "background, no border, and centered bold text so the diagram "
        "reads as a deck slide rather than an anonymous box-and-line."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "diagram": {"type": "string", "description": "Diagram filename."},
            "title": {
                "type": "string",
                "description": (
                    "Main banner text (large, bold). Use the surgical "
                    "story's Title: line verbatim, or a short rewrite."
                ),
            },
            "subtitle": {
                "type": "string",
                "description": (
                    "Optional smaller line below the title. Good for "
                    "`PROJ-126 — short tagline` or a one-line summary."
                ),
            },
            "width": {
                "type": "number",
                "description": (
                    "Banner width in pixels. Default 1540 fits a 6-column "
                    "swimlane layout. Pass a different value if you have "
                    "more or fewer containers."
                ),
            },
            "x": {"type": "number"},
            "y": {"type": "number"},
        },
        "required": ["diagram", "title"],
        "additionalProperties": False,
    },
)


async def add_title(args: dict[str, Any], cfg: ServerConfig) -> dict[str, Any]:
    diagram_name = str(args.get("diagram") or "")
    title_text = str(args.get("title") or "")
    if not diagram_name or not title_text:
        raise ValueError("`diagram` and `title` are required.")

    subtitle_text = args.get("subtitle")
    store = DiagramStore(cfg.diagrams_dir)
    diagram = store.load(diagram_name)

    x = _num_or(args.get("x"), _TITLE_X)
    y = _num_or(args.get("y"), _TITLE_Y)
    width = _num_or(args.get("width"), _TITLE_W)

    title_id = _next_id([n.id for n in diagram.nodes], "title")
    diagram.nodes.append(
        DiagramNode(
            id=title_id,
            label=title_text,
            shape="rectangle",  # ignored — raw_style overrides
            x=x,
            y=y,
            width=width,
            height=_TITLE_H,
            raw_style=TITLE_STYLE,
        )
    )

    result: dict[str, Any] = {
        "id": title_id,
        "path": store.save(diagram_name, diagram),
    }

    if subtitle_text:
        # Re-load so the subtitle's id collision check sees the title.
        diagram = store.load(diagram_name)
        subtitle_id = _next_id([n.id for n in diagram.nodes], "subtitle")
        diagram.nodes.append(
            DiagramNode(
                id=subtitle_id,
                label=str(subtitle_text),
                shape="rectangle",
                x=x,
                y=y + _SUBTITLE_Y_OFFSET,
                width=width,
                height=_SUBTITLE_H,
                raw_style=SUBTITLE_STYLE,
            )
        )
        result["subtitle_id"] = subtitle_id
        result["path"] = store.save(diagram_name, diagram)

    return result


def _num_or(v: Any, fallback: float) -> float:
    try:
        return float(v) if v is not None else fallback
    except (TypeError, ValueError):
        return fallback


def _next_id(existing: list[str], prefix: str) -> str:
    taken = set(existing)
    if prefix not in taken:
        return prefix
    i = 2
    while f"{prefix}{i}" in taken:
        i += 1
    return f"{prefix}{i}"
