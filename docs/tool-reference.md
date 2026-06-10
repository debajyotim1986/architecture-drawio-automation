# MCP tool reference — `drawio` server

All tools are registered in
[`drawio-mcp-server/src/drawio_mcp_server/tools/__init__.py`](../drawio-mcp-server/src/drawio_mcp_server/tools/__init__.py).

All 13 tools are registered via `TOOL_REGISTRY` in
[`tools/__init__.py`](../drawio-mcp-server/src/drawio_mcp_server/tools/__init__.py).

### Read-only

| Tool | Purpose | Required args |
|---|---|---|
| `list_diagrams` | List `.drawio` files in `diagrams/` | — |
| `read_diagram` | Full structured diagram (nodes + edges + geometry) | `name` |
| `read_diagram_summary` | Compact label-only view (preferred for reasoning) | `name` |
| `list_stories` | List Jira story files in `jira-stories/` | — |
| `read_story` | Read a Jira story file's text | `name` |

### Mutating

| Tool | Purpose | Required args |
|---|---|---|
| `create_diagram` | Create a new empty `.drawio` file | `name` |
| `add_container` | Create a labeled swimlane column (140-px gap, 1080-px tall) | `diagram`, `label` |
| `add_node` | Add one shape; resolves `gcp_icon`; auto-stacks inside a container at 200-px stride | `diagram`, `label` |
| `add_edge` | Connect two nodes; runs 5 routing passes; frames busy nodes (degree > 3) | `diagram`, `from`, `to` |
| `add_title` | Stamp a bold banner above the swimlanes | `diagram`, `title` |
| `add_connector_table` | Embed the 14-column connector-detail table below the swimlanes (hard-fails on `{TBD}`) | `diagram`, `story` |
| `update_node` | Patch an existing node (label, shape, position, icon) | `diagram`, `id` |
| `remove_element` | Delete a node (cascades to its edges) or a single edge | `diagram`, `id` |

## Shape vocabulary (`add_node` / `update_node`)

| Value | Renders as | Use for |
|---|---|---|
| `rectangle` | square box | generic component |
| `rounded` | rounded box | service / API |
| `process` | bracketed box | business process / pipeline stage |
| `ellipse` | oval | use case / abstract concept |
| `cylinder` | disk stack | database |
| `queue` | delay shape | message broker, queue, topic |
| `cloud` | cloud | external SaaS / third party |
| `actor` | UML stick figure | end user / persona |
| `hexagon` | hexagon | gateway / proxy / boundary |
| `document` | doc shape | report, spec, output artifact |
| `container` | dashed group box | logical grouping (parent of other nodes) |

The full mapping from these names to draw.io's `style=` strings lives in
[`drawio-mcp-server/src/drawio_mcp_server/drawio/shapes.py`](../drawio-mcp-server/src/drawio_mcp_server/drawio/shapes.py).
Add new shapes there in two places (`SHAPE_STYLES` + `DEFAULT_SIZE`) and
extend the `NodeShape` literal in
[`src/drawio_mcp_server/types.py`](../drawio-mcp-server/src/drawio_mcp_server/types.py).

## Error contract

Every tool raises on failure and the server wraps the error into an MCP
text response prefixed with `Error in <tool_name>:`. Common errors:

- `` `name` is required `` — caller missed a required argument.
- `Refusing path outside diagrams root: …` — path traversal attempt.
- `Diagram payload appears compressed/encoded` — file was saved with
  draw.io's *Compressed* option on; re-save uncompressed.
- `No node with id 'x'` / `No node matches 'x'` — referenced element doesn't
  exist; call `read_diagram_summary` first.
