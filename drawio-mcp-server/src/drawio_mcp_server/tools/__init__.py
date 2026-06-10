"""Tool registry — every MCP tool is defined in its own module here.

`TOOL_REGISTRY` maps tool name → (Tool definition, handler callable). The
server wires this up in server.py via `list_tools()` / `call_tool()`.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from mcp.types import Tool

from ..util.config import ServerConfig
from .add_connector_table import add_connector_table, add_connector_table_tool
from .add_container import add_container, add_container_tool
from .add_edge import add_edge, add_edge_tool
from .add_node import add_node, add_node_tool
from .add_title import add_title, add_title_tool
from .create_diagram import create_diagram, create_diagram_tool
from .list_diagrams import list_diagrams, list_diagrams_tool
from .list_stories import list_stories, list_stories_tool
from .read_diagram import read_diagram, read_diagram_tool
from .read_story import read_story, read_story_tool
from .read_summary import read_diagram_summary, read_diagram_summary_tool
from .remove_element import remove_element, remove_element_tool
from .update_node import update_node, update_node_tool

Handler = Callable[[dict[str, Any], ServerConfig], Awaitable[Any]]

TOOL_REGISTRY: dict[str, tuple[Tool, Handler]] = {
    "list_diagrams": (list_diagrams_tool, list_diagrams),
    "read_diagram": (read_diagram_tool, read_diagram),
    "read_diagram_summary": (read_diagram_summary_tool, read_diagram_summary),
    "create_diagram": (create_diagram_tool, create_diagram),
    "add_title": (add_title_tool, add_title),
    "add_container": (add_container_tool, add_container),
    "add_node": (add_node_tool, add_node),
    "add_edge": (add_edge_tool, add_edge),
    "add_connector_table": (add_connector_table_tool, add_connector_table),
    "update_node": (update_node_tool, update_node),
    "remove_element": (remove_element_tool, remove_element),
    "list_stories": (list_stories_tool, list_stories),
    "read_story": (read_story_tool, read_story),
}


def all_tool_definitions() -> list[Tool]:
    return [t for t, _ in TOOL_REGISTRY.values()]


async def dispatch_tool(
    name: str, args: dict[str, Any], cfg: ServerConfig
) -> Any:
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}")
    _, handler = TOOL_REGISTRY[name]
    return await handler(args or {}, cfg)
