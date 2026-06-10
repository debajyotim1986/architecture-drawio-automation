# drawio-mcp-server

Local **Model Context Protocol** server (Python) exposing a small,
intent-level tool surface for reading and modifying `.drawio` architecture
diagrams.

Designed to be invoked over stdio by GitHub Copilot Chat (VS Code) or any
other MCP-aware client. See the parent [README](../README.md) for the
end-to-end Jira-story → diagram workflow.

## Install & run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Run the server (it speaks MCP over stdio — useful only when launched by
# an MCP client; running it standalone just blocks waiting for input).
python -m drawio_mcp_server
# or, after `pip install -e .`, the equivalent console script:
drawio-mcp-server
```

Environment variables:

| Var | Default | Purpose |
|---|---|---|
| `DRAWIO_DIAGRAMS_DIR` | `<cwd>/diagrams` | where `.drawio` files live |
| `DRAWIO_STORIES_DIR` | `<cwd>/jira-stories` | where Jira story files live |

## Source layout

```
src/drawio_mcp_server/
├── __init__.py
├── __main__.py            # entry: `python -m drawio_mcp_server`
├── server.py              # MCP server: list_tools / call_tool + stdio
├── types.py               # Diagram / DiagramNode / DiagramEdge (pydantic)
├── tools/
│   ├── __init__.py        # tool registry + dispatcher
│   ├── list_diagrams.py
│   ├── read_diagram.py
│   ├── read_summary.py
│   ├── create_diagram.py
│   ├── add_node.py
│   ├── add_edge.py
│   ├── update_node.py
│   ├── remove_element.py
│   ├── list_stories.py
│   └── read_story.py
├── drawio/
│   ├── parser.py          # mxGraph XML  → Diagram model
│   ├── builder.py         # Diagram model → mxGraph XML
│   ├── shapes.py          # shape vocabulary + default sizes
│   └── summarize.py       # full Diagram → compact DiagramSummary
└── util/
    ├── config.py          # env-driven config
    ├── diagram_store.py   # sandboxed FS access for diagrams
    └── story_store.py     # sandboxed FS access for stories
```

## Adding a new tool

1. Create `src/drawio_mcp_server/tools/my_tool.py`. Export a
   `Tool` instance (`name`, `description`, `inputSchema`) and an async
   handler `(args: dict, cfg: ServerConfig) -> Any`.
2. Register both in `tools/__init__.py` (`TOOL_REGISTRY` map).
3. Document it in [`docs/tool-reference.md`](../docs/tool-reference.md).
4. Reload the MCP server in VS Code (it auto-restarts when you change the
   `.py` files because the launcher reimports them on each connection).

The handler can return any JSON-serializable value — `server.py` wraps it
into an MCP `TextContent` block automatically.

## Status

Core read/write tools are implemented against the **uncompressed**
`.drawio` XML form. Compressed payloads (deflate+base64) are not yet
supported — see the error message in
[`drawio/parser.py`](src/drawio_mcp_server/drawio/parser.py) for guidance.
