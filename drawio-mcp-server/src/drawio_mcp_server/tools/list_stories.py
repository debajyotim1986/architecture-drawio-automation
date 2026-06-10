from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..util.config import ServerConfig
from ..util.story_store import StoryStore

list_stories_tool = Tool(
    name="list_stories",
    description=(
        "List downloaded Jira story files (.txt, .md, .json) available in the "
        "stories drop folder. Results are sorted in natural-ascending "
        "(low-to-high) order so Jira-style keys order intuitively: "
        "PROJ-2 before PROJ-10 before PROJ-100. When the user asks you to "
        "process 'all stories' or 'every story in order', call this tool "
        "first and process the result in the order returned, unless the user "
        "specifies a different sequence."
    ),
    inputSchema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)


async def list_stories(_args: dict[str, Any], cfg: ServerConfig) -> dict[str, list[str]]:
    return {"stories": StoryStore(cfg.stories_dir).list()}
