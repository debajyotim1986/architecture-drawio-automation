"""MCP server wiring — list_tools / call_tool handlers + stdio transport."""

from __future__ import annotations

import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .tools import all_tool_definitions, dispatch_tool
from .util.config import resolve_config

server: Server = Server("drawio-mcp-server")


@server.list_tools()
async def _list_tools() -> list[Tool]:
    return all_tool_definitions()


@server.call_tool()
async def _call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    cfg = resolve_config()
    try:
        result = await dispatch_tool(name, arguments or {}, cfg)
    except Exception as exc:  # surfaced back to the LLM as the tool's error
        return [TextContent(type="text", text=f"Error in {name}: {exc}")]

    if isinstance(result, str):
        return [TextContent(type="text", text=result)]
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


async def run() -> None:
    cfg = resolve_config()
    # stderr only — stdout is reserved for the MCP transport
    print(
        f"[drawio-mcp] connected. diagrams={cfg.diagrams_dir} stories={cfg.stories_dir}",
        file=sys.stderr,
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
