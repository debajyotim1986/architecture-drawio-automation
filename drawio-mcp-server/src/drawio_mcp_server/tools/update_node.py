from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..drawio.gcp_icons import build_gcp_image_style, resolve_icon
from ..drawio.shapes import DEFAULT_SIZE
from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

update_node_tool = Tool(
    name="update_node",
    description=(
        "Patch an existing node — rename it, change its shape, swap in a GCP "
        "icon, move it, or resize it. Only the fields you supply are updated. "
        "Identify the node by id."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "diagram": {"type": "string"},
            "id": {"type": "string", "description": "Id of the node to patch."},
            "label": {"type": "string"},
            "shape": {"type": "string", "enum": list(DEFAULT_SIZE.keys())},
            "gcp_icon": {
                "type": "string",
                "description": (
                    "Swap the node to an official GCP icon (e.g. 'BigQuery', "
                    "'Cloud Run', 'pubsub'). Resizes to 64x64 unless width/"
                    "height are also given. Clears any prior raw style."
                ),
            },
            "style": {
                "type": "string",
                "description": "Replace the node's draw.io style verbatim.",
            },
            "clear_icon": {
                "type": "boolean",
                "description": (
                    "Drop any custom style (GCP icon or raw style) and fall "
                    "back to the stencil indicated by `shape`."
                ),
            },
            "x": {"type": "number"},
            "y": {"type": "number"},
            "width": {"type": "number"},
            "height": {"type": "number"},
        },
        "required": ["diagram", "id"],
        "additionalProperties": False,
    },
)


async def update_node(args: dict[str, Any], cfg: ServerConfig) -> dict[str, str]:
    diagram_name = str(args.get("diagram") or "")
    node_id = str(args.get("id") or "")
    if not diagram_name or not node_id:
        raise ValueError("`diagram` and `id` are required.")

    store = DiagramStore(cfg.diagrams_dir)
    diagram = store.load(diagram_name)
    node = next((n for n in diagram.nodes if n.id == node_id), None)
    if node is None:
        raise ValueError(f"No node with id '{node_id}'.")

    if "label" in args:
        node.label = str(args["label"])
    if "shape" in args:
        node.shape = str(args["shape"])  # type: ignore[assignment]
    for field in ("x", "y", "width", "height"):
        if field in args:
            setattr(node, field, float(args[field]))

    if args.get("clear_icon"):
        node.raw_style = None
    if args.get("gcp_icon"):
        svg = resolve_icon(str(args["gcp_icon"]), cfg.icons_dir)
        if svg is None:
            raise ValueError(
                f"Unknown gcp_icon '{args['gcp_icon']}'. No matching SVG under "
                f"{cfg.icons_dir}."
            )
        node.raw_style = build_gcp_image_style(svg)
        # Default to icon-friendly size if caller didn't override.
        if "width" not in args:
            node.width = 64.0
        if "height" not in args:
            node.height = 64.0
    elif "style" in args:
        node.raw_style = str(args["style"])

    return {"path": store.save(diagram_name, diagram)}
