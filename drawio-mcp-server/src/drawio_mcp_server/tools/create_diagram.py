from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from mcp.types import Tool

from ..types import Diagram
from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

create_diagram_tool = Tool(
    name="create_diagram",
    description=(
        "Create a new empty *.drawio file. Either `name` or `jira_key` is "
        "required. When `jira_key` is given (and `name` is not), the server "
        "generates a unique filename `<JIRA_KEY>-YYYYMMDD-HHMMSS.drawio` so "
        "running the same prompt repeatedly produces distinct diagrams without "
        "overwriting prior ones. Fails if the resolved file already exists "
        "unless overwrite=true. Returns the resolved name and path."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": (
                    "Explicit filename, with or without .drawio. Takes "
                    "precedence over `jira_key` when both are given."
                ),
            },
            "jira_key": {
                "type": "string",
                "description": (
                    "Jira key (e.g. 'PROJ-123'). When supplied without `name`, "
                    "the server builds the filename as "
                    "'<JIRA_KEY>-YYYYMMDD-HHMMSS.drawio' using the current UTC "
                    "time so re-runs do not collide. Accepts the key with or "
                    "without a trailing '.txt'."
                ),
            },
            "title": {"type": "string", "description": "Diagram tab title shown inside draw.io."},
            "overwrite": {"type": "boolean", "default": False},
        },
        "required": [],
        "additionalProperties": False,
    },
)


_JIRA_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*-\d+$")


async def create_diagram(args: dict[str, Any], cfg: ServerConfig) -> dict[str, str]:
    explicit_name = str(args.get("name") or "").strip()
    jira_key_raw = str(args.get("jira_key") or "").strip()

    if not explicit_name and not jira_key_raw:
        raise ValueError("Either `name` or `jira_key` is required.")

    if explicit_name:
        name = explicit_name
    else:
        # Tolerate "PROJ-123.txt" or "proj-123" — normalise to "PROJ-123".
        key = jira_key_raw.removesuffix(".txt").removesuffix(".md").strip()
        if not _JIRA_KEY_RE.match(key):
            raise ValueError(
                f"`jira_key` does not look like a Jira key: {jira_key_raw!r}. "
                "Expected something like 'PROJ-123'."
            )
        key = key.upper()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        name = f"{key}-{stamp}.drawio"

    title = str(args.get("title") or name.removesuffix(".drawio"))
    overwrite = bool(args.get("overwrite", False))

    store = DiagramStore(cfg.diagrams_dir)
    if not overwrite and store.exists(name):
        raise ValueError(
            f"Diagram already exists: {name}. Pass overwrite=true to replace it, "
            "or use add_node / update_node to amend it."
        )
    path = store.save(name, Diagram(name=title, nodes=[], edges=[]))
    return {"name": name, "path": path}
