from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

read_diagram_tool = Tool(
    name="read_diagram",
    description=(
        "Load a draw.io diagram and return its full structured representation "
        "(nodes + edges + geometry). Use read_diagram_summary instead if you "
        "only need to reason about the topology — it is much smaller."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Diagram filename, with or without .drawio extension.",
            }
        },
        "required": ["name"],
        "additionalProperties": False,
    },
)


async def read_diagram(args: dict[str, Any], cfg: ServerConfig) -> dict[str, Any]:
    name = str(args.get("name") or "")
    if not name:
        raise ValueError("`name` is required.")
    diagram = DiagramStore(cfg.diagrams_dir).load(name)
    return diagram.model_dump()
