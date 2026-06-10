from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

list_diagrams_tool = Tool(
    name="list_diagrams",
    description=(
        "List all *.drawio architecture diagrams available in the workspace. "
        "Call this first when you don't yet know which diagram to read or update. "
        "Results are natural-sorted so versioned names order intuitively "
        "(payments-v2.drawio before payments-v10.drawio)."
    ),
    inputSchema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)


async def list_diagrams(_args: dict[str, Any], cfg: ServerConfig) -> dict[str, list[str]]:
    return {"diagrams": DiagramStore(cfg.diagrams_dir).list()}
