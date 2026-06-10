from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..drawio.gcp_icons import (
    build_gcp_image_style,
    detect_icon_from_label,
    resolve_icon,
)
from ..drawio.shapes import DEFAULT_SIZE
from ..types import DiagramNode
from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

SHAPE_ENUM = list(DEFAULT_SIZE.keys())

# Grid auto-layout. GCP icons are 64x64 with a label rendered *below* the
# icon, so we reserve enough vertical room for ~2 lines of label text and
# enough horizontal room that long labels (e.g. "Order Events (Pub/Sub)" or
# "BigQuery audited tables") don't collide with the next column.
#
# Strides are deliberately generous: edge labels sit *above* the connector
# (see DEFAULT_EDGE_STYLE), so the row stride must also leave a clear lane
# between rows for the label + a few px of margin. With 360x320 a node
# label and an inbound edge label never share the same y band.
_GRID_COLS = 4
_GRID_ORIGIN_X = 60.0
_GRID_ORIGIN_Y = 80.0
_GRID_COL_STRIDE = 360.0
_GRID_ROW_STRIDE = 320.0
_GCP_ICON_SIZE = 64.0

add_node_tool = Tool(
    name="add_node",
    description=(
        "Add a single shape (component, service, db, queue, actor, ...) to a "
        "diagram. Position is optional — if omitted, the node is auto-placed "
        "on a wrap-around grid with enough spacing for icon-with-label nodes. "
        "For Google Cloud services prefer `gcp_icon` (e.g. 'BigQuery', "
        "'Cloud Run', 'pubsub') over a generic shape — the server embeds the "
        "official GCP SVG so it renders inside the VS Code draw.io extension. "
        "Safety net: if you omit `gcp_icon` but the label clearly names a GCP "
        "service (e.g. 'Dashboard (Cloud Run)', 'Orders DB - Cloud SQL', "
        "'BigQuery analytics'), the server auto-applies the matching icon and "
        "returns it as `auto_detected_gcp_icon`. Pass `shape='actor'` (or "
        "'container') to opt out of auto-detection when you want a stencil. "
        "Returns the assigned node id."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "diagram": {"type": "string", "description": "Diagram filename."},
            "label": {"type": "string", "description": "Visible text on the shape."},
            "shape": {
                "type": "string",
                "enum": SHAPE_ENUM,
                "description": (
                    "Visual stencil. Use cylinder for databases, queue for message "
                    "brokers, actor for users, cloud for external services. Ignored "
                    "when `gcp_icon` or `style` is provided."
                ),
            },
            "gcp_icon": {
                "type": "string",
                "description": (
                    "GCP service name (case/space/underscore-insensitive): "
                    "'BigQuery', 'Cloud Run', 'cloud_sql', 'pubsub', 'GKE', "
                    "'Vertex AI', etc. When set the server resolves the SVG, "
                    "inlines it as a URL-encoded data URI, and sets size to "
                    "64x64 unless width/height are given. Takes precedence over "
                    "`shape`."
                ),
            },
            "style": {
                "type": "string",
                "description": (
                    "Escape hatch: full draw.io style string. Use only when "
                    "neither `shape` nor `gcp_icon` fits. Bypasses the shape "
                    "table verbatim."
                ),
            },
            "id": {"type": "string", "description": "Optional stable id; auto-generated if omitted."},
            "x": {"type": "number"},
            "y": {"type": "number"},
            "width": {"type": "number"},
            "height": {"type": "number"},
            "parent_id": {
                "type": "string",
                "description": "Id of a `container` node to nest this shape inside.",
            },
        },
        "required": ["diagram", "label"],
        "additionalProperties": False,
    },
)


async def add_node(args: dict[str, Any], cfg: ServerConfig) -> dict[str, str]:
    diagram_name = str(args.get("diagram") or "")
    label = str(args.get("label") or "")
    if not diagram_name or not label:
        raise ValueError("`diagram` and `label` are required.")

    gcp_icon = args.get("gcp_icon")
    raw_style = args.get("style")
    shape = args.get("shape")
    auto_detected = False

    # Auto-detect: when the caller didn't explicitly request a GCP icon or a
    # raw style, scan the label for a known GCP service name. This is the
    # safety net for models that forget the `gcp_icon` parameter — a label
    # like "Dashboard (Cloud Run)" or "BigQuery audited tables" picks up the
    # right icon automatically. The `shape` field is treated as a hint, not a
    # veto: actors, plain containers, and swimlanes opt out so users / layer
    # boxes stay as their stencil.
    if not gcp_icon and not raw_style:
        shape_hint = str(shape or "")
        if shape_hint not in {"actor", "container", "swimlane"}:
            detected = detect_icon_from_label(label)
            if detected:
                gcp_icon = detected
                auto_detected = True

    # If neither gcp_icon nor a raw style is provided, fall back to a stencil
    # shape (default to "rectangle" rather than failing — keeps the LLM
    # forgiving when it forgets the shape).
    if not gcp_icon and not raw_style:
        shape = str(shape or "rectangle")
        if shape not in DEFAULT_SIZE:
            raise ValueError(f"Unknown shape '{shape}'. Use one of {SHAPE_ENUM}.")

    store = DiagramStore(cfg.diagrams_dir)
    diagram = store.load(diagram_name)

    node_id = str(args.get("id") or _next_id([n.id for n in diagram.nodes], "n"))

    # Resolve gcp_icon -> raw_style. Done after diagram load so a bad icon
    # name doesn't corrupt the file.
    if gcp_icon:
        svg = resolve_icon(str(gcp_icon), cfg.icons_dir)
        if svg is None:
            raise ValueError(
                f"Unknown gcp_icon '{gcp_icon}'. No matching SVG under "
                f"{cfg.icons_dir}. Pass a known service name (e.g. 'BigQuery', "
                f"'Cloud Run', 'pubsub') or omit gcp_icon and use `shape`."
            )
        raw_style = build_gcp_image_style(svg)
        default_w, default_h = _GCP_ICON_SIZE, _GCP_ICON_SIZE
        # shape is irrelevant when raw_style is set, but the Pydantic model
        # still requires a literal — pick the closest neutral.
        shape = shape or "rectangle"
    elif raw_style:
        default_w, default_h = 80.0, 80.0
        shape = shape or "rectangle"
    else:
        default_w, default_h = DEFAULT_SIZE[shape]  # type: ignore[index]

    parent_id = str(args["parent_id"]) if args.get("parent_id") else None
    if parent_id:
        place_x, place_y = _auto_place_in_container(diagram.nodes, parent_id)
    else:
        place_x, place_y = _auto_place(diagram.nodes)

    diagram.nodes.append(
        DiagramNode(
            id=node_id,
            label=label,
            shape=shape,  # type: ignore[arg-type]
            x=_num_or(args.get("x"), place_x),
            y=_num_or(args.get("y"), place_y),
            width=_num_or(args.get("width"), default_w),
            height=_num_or(args.get("height"), default_h),
            parent_id=parent_id,
            raw_style=str(raw_style) if raw_style else None,
        )
    )

    result: dict[str, str] = {"id": node_id, "path": store.save(diagram_name, diagram)}
    if auto_detected and gcp_icon:
        result["auto_detected_gcp_icon"] = str(gcp_icon)
    return result


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


def _auto_place(nodes: list[DiagramNode]) -> tuple[float, float]:
    """Wrap-around grid placement so labels and icons don't collide.

    Counts non-container, non-swimlane, non-child nodes (top-level
    nodes that need a grid slot). Containers and swimlanes are
    background frames; children of a container have their own
    coordinate space and are laid out by `_auto_place_in_container`.
    """
    placed = [
        n for n in nodes
        if n.shape not in ("container", "swimlane") and not n.parent_id
    ]
    idx = len(placed)
    col = idx % _GRID_COLS
    row = idx // _GRID_COLS
    return (
        _GRID_ORIGIN_X + col * _GRID_COL_STRIDE,
        _GRID_ORIGIN_Y + row * _GRID_ROW_STRIDE,
    )


# When a node is nested inside a container/swimlane its x/y are RELATIVE
# to the container's top-left. We stack children vertically inside the
# container body (skipping the header strip) with enough room per child
# for a 64px GCP icon plus its label below AND a clear horizontal
# "lane" between rows that fits MULTIPLE parallel connector labels
# without sharing Y space with the icon-name label band.
#
# Layout maths (stride = 200):
#   icon body          = y .. y + 64
#   icon label band    = y + 64 .. y + 80   (~16px tall, "Cloud Composer")
#   connector lane     = y + 80 .. y + 200  (120px → fits up to 7 stacked
#                                              edge labels at 16px each
#                                              without touching the icon
#                                              label band above).
# Previous stride 150 gave only 86px for the connector lane — that left
# 7-edge clusters with overlapping connector labels and the topmost
# label butting against the icon label band below.
_CONTAINER_CHILD_X = 16.0          # left padding inside the container
_CONTAINER_CHILD_Y0 = 50.0         # below the 30px header + a bit of padding
_CONTAINER_CHILD_STRIDE = 200.0    # 64 icon + 16 icon-label + 120 connector lane


def _auto_place_in_container(
    nodes: list[DiagramNode], parent_id: str
) -> tuple[float, float]:
    """Stack a container's children vertically, starting below its header."""
    siblings = [n for n in nodes if n.parent_id == parent_id]
    idx = len(siblings)
    return (
        _CONTAINER_CHILD_X,
        _CONTAINER_CHILD_Y0 + idx * _CONTAINER_CHILD_STRIDE,
    )
