from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..util.config import ServerConfig
from ..util.story_store import StoryStore

read_story_tool = Tool(
    name="read_story",
    description=(
        "Read the full text of a downloaded Jira story file from the stories "
        "drop folder. Use this to extract the architectural requirement before "
        "deciding which diagram to create or modify."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Story filename, e.g. 'PROJ-123.txt'."}
        },
        "required": ["name"],
        "additionalProperties": False,
    },
)


async def read_story(args: dict[str, Any], cfg: ServerConfig) -> dict[str, str]:
    name = str(args.get("name") or "")
    if not name:
        raise ValueError("`name` is required.")
    return {"name": name, "content": StoryStore(cfg.stories_dir).read(name)}
