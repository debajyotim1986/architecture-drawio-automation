from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

remove_element_tool = Tool(
    name="remove_element",
    description=(
        "Delete a node or edge by id. Removing a node also removes any edges "
        "incident to it (so the diagram stays consistent)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "diagram": {"type": "string"},
            "id": {"type": "string"},
        },
        "required": ["diagram", "id"],
        "additionalProperties": False,
    },
)


async def remove_element(args: dict[str, Any], cfg: ServerConfig) -> dict[str, str]:
    diagram_name = str(args.get("diagram") or "")
    target_id = str(args.get("id") or "")
    if not diagram_name or not target_id:
        raise ValueError("`diagram` and `id` are required.")

    store = DiagramStore(cfg.diagrams_dir)
    diagram = store.load(diagram_name)

    node_idx = next((i for i, n in enumerate(diagram.nodes) if n.id == target_id), None)
    if node_idx is not None:
        del diagram.nodes[node_idx]
        diagram.edges = [
            e for e in diagram.edges if e.source_id != target_id and e.target_id != target_id
        ]
        return {"removed": "node", "path": store.save(diagram_name, diagram)}

    edge_idx = next((i for i, e in enumerate(diagram.edges) if e.id == target_id), None)
    if edge_idx is not None:
        del diagram.edges[edge_idx]
        return {"removed": "edge", "path": store.save(diagram_name, diagram)}

    raise ValueError(f"No node or edge with id '{target_id}'.")
