from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..drawio.summarize import summarize
from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

read_diagram_summary_tool = Tool(
    name="read_diagram_summary",
    description=(
        "Return a compact, label-only summary of a diagram (node labels + "
        "edge from→to). Prefer this over read_diagram when you only need to "
        "decide whether to add, remove, or rename components."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Diagram filename."}
        },
        "required": ["name"],
        "additionalProperties": False,
    },
)


async def read_diagram_summary(args: dict[str, Any], cfg: ServerConfig) -> dict[str, Any]:
    name = str(args.get("name") or "")
    if not name:
        raise ValueError("`name` is required.")
    diagram = DiagramStore(cfg.diagrams_dir).load(name)
    return summarize(diagram).model_dump(by_alias=True)
