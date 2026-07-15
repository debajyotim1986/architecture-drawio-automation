---
name: maintain-drawio-mcp
description: >-
  Orientation + change-recipes for the Architecture Copilot / drawio-mcp-server
  codebase (a local MCP server that turns Jira requirements into draw.io
  architecture diagrams). Use whenever modifying, extending, or debugging this
  repo: adding or changing MCP tools, GCP icons or the service-name labels,
  diagram layout / edge routing / XML rendering, the normalizer / verifier /
  connector-detail scripts, the copy-paste prompts, or the restricted-service
  policy. Read this first before editing under drawio-mcp-server/ or scripts/.
---

# Maintaining the Architecture Copilot (drawio-mcp-server)

A local Python **MCP server** that turns a plain-English Jira requirement into a
deck-quality **draw.io** architecture diagram, driven from one GitHub Copilot
Chat prompt. The LLM names *intent* (add a container, add a node, connect an
edge); the server owns all geometry, icons, layout, and file I/O behind a path
sandbox. An offline CLI toolchain normalizes the story, fills a connector
contract, and gates quality before delivery.

> Authoritative deep-dive lives in [`docs/HLA.html`](../../../docs/HLA.html)
> (architecture + the 9-stage flow) and [`README.md`](../../../README.md).
> Paths below are relative to the repo root.

## Where things live

| Path | Purpose |
|---|---|
| `drawio-mcp-server/src/drawio_mcp_server/server.py` | MCP entry: `@list_tools` / `@call_tool` stdio JSON-RPC loop, dispatch |
| `drawio-mcp-server/src/drawio_mcp_server/tools/` | **One file per MCP tool** + `__init__.py` `TOOL_REGISTRY` (name → (Tool, handler)) |
| `drawio-mcp-server/src/drawio_mcp_server/drawio/` | Domain model ⇄ mxGraph XML: `types.py`, `parser.py`, `builder.py`, `shapes.py`, `gcp_icons.py`, `summarize.py` |
| `drawio-mcp-server/src/drawio_mcp_server/util/` | `config.py` (ServerConfig: diagrams/stories/icons dirs), `diagram_store.py` + `story_store.py` (path-sandboxed), `natural_sort.py` |
| `scripts/` | `normalize_jira_story.py`, `verify_mcp.py`, `generate_connector_details.py`, `reroute_diagram.py` + per-OS wrappers (`linux/ mac/ windows/`) |
| `prompts/` | `create-diagram.md` (PRIMARY 12-step flow), `update-diagram.md` |
| `logo_icon_gcp/` | 258 official GCP SVGs — icon catalog (folder-per-service) |
| `policy/unavailable_services.md` | Restricted-service ban list + alternatives table (the guardrail source of truth) |
| `.github/copilot-instructions.md` | Repo-wide Copilot rules (shorthand router, swimlanes-first, GCP-icon rule, zero-TBD) |
| `template/`, `examples/`, `jira-stories/`, `diagrams/` | Story templates / samples / inputs / generated outputs |

## Request path (runtime)

`Copilot Chat → server.py (stdio) → TOOL_REGISTRY dispatch → tool handler →
DiagramStore/StoryStore (sandboxed) → drawio/parser+builder → .drawio file`.
Read-only tools (`list_diagrams`, `read_diagram`, `read_diagram_summary`,
`list_stories`, `read_story`) never mutate; the 8 mutating tools
(`create_diagram`, `add_container`, `add_node`, `add_edge`,
`add_connector_table`, `add_title`, `update_node`, `remove_element`) load →
edit the Pydantic `Diagram` → `store.save` (re-serialize whole file).

## Domain & rendering — the load-bearing code

- **`types.py`** — Pydantic `Diagram` / `DiagramNode` / `DiagramEdge`. A node's
  `raw_style` (when set) overrides the shape table; `label` is the semantic
  text.
- **`parser.py` ⇄ `builder.py`** — round-trip `.drawio` ⇄ model. `builder.py`
  emits **uncompressed** mxGraph XML, escapes every value with `quoteattr`, and
  relies on `html=1` labels. Two edge-label mechanisms are deliberate: the step
  number is rendered *into* the label (`"N. action"`) and an
  `<mxPoint x="0" y="-22" as="offset"/>` physically lifts the label 22px above
  the line. **Round-trip tests (`tests/test_parser.py`) must stay green.**
- **`shapes.py`** — `SHAPE_STYLES`, `DEFAULT_SIZE`, `SWIMLANE_COLORS`,
  `DEFAULT_EDGE_STYLE`, and `REQUIRED_ARROW_KEYS`. The edge style comments are
  load-bearing (arrowhead fill, jettySize routing, label colour/pill).
- **`gcp_icons.py`** — `GCP_ICON_PATHS` (curated name→SVG) with a
  `<snake>/<snake>.svg` fallback; `build_gcp_image_style` inlines the SVG as a
  **URL-encoded `data:image/svg+xml,` URI** (NOT base64 — the VS Code drawio
  extension can't parse `;base64,`); `detect_icon_from_label` auto-detects a
  service from a label; `GCP_SERVICE_NAMES` + `label_with_service` /
  `strip_service_suffix` append the canonical service name beside each icon.
- **`summarize.py`** — compact id+label view for cheap LLM reasoning.

## Layout constants (single source of truth for spacing)

Tune spacing *here*, never by passing x/y from the prompt:

- `tools/add_container.py`: `_COLUMN_ORIGIN_X=40`, `_COLUMN_GAP=140`, width 240.
- `tools/add_node.py`: top-level grid `_GRID_*`; in-container
  `_CONTAINER_CHILD_X=16`, `_CONTAINER_CHILD_Y0=50`,
  `_CONTAINER_CHILD_STRIDE=200`, `_GCP_ICON_SIZE=64`.
- `tools/add_edge.py`: `_CHILD_STRIDE=200`, `_CORRIDOR_INSET=70`,
  `_LANE_BAND_HALF=50`, `_FAN_OUT_SPREAD=0.6`, `_ROW_GAP_*`; `_frame_busy_nodes`
  wraps a >3-degree node in a "card" border.
- `shapes.py` `DEFAULT_SIZE["swimlane"] = (240, 1080)` (holds ~5 stacked icons).

These interlock — the container gap (140), child stride (200), and corridor
inset (70) are chosen so the orthogonal edge router bends in the gap between
swimlanes, never over an icon. Change one, re-check edge routing.

## Invariants — break these and diagrams silently render wrong

1. **Uncompressed XML + URL-encoded SVG data URIs only.** No compression, no
   `;base64,`.
2. **Every edge needs `endArrow=...;endFill=1`.** Keep `REQUIRED_ARROW_KEYS`
   (shapes.py) in sync with `DEFAULT_EDGE_STYLE`; `verify_mcp.py` hard-fails on
   arrowless edges.
3. **GCP icon nodes use `verticalLabelPosition=bottom;verticalAlign=top`** so
   the label sits below the 64×64 icon.
4. **Keep `DiagramNode.label` plain text.** It feeds the verifier's
   duplicate-label check, the connector-details table, and summaries — do NOT
   bake HTML/`<br>` into it (that's why service names are appended as plain
   `" (Cloud SQL)"`, not styled markup).
5. **Path sandbox.** `DiagramStore`/`StoryStore` reject any path outside their
   root. In ad-hoc tests on macOS, wrap tmp dirs in `Path(...).resolve()` or the
   `/var`→`/private/var` symlink trips the sandbox.
6. **Gates.** `verify_mcp.py` exit 2 = do not ship; `add_connector_table` has a
   zero-`{TBD}` pre-flight guard.
7. **Filenames** are timestamped by `create_diagram`
   (`<JIRA_KEY>-YYYYMMDD-HHMMSS.drawio`) so re-runs never overwrite.

## Common changes (recipes)

- **Add an MCP tool** → create `tools/<name>.py` (a `Tool` schema + async
  `handler(args, cfg)`), register it in `tools/__init__.py` `TOOL_REGISTRY`, and
  bump the expected-tool count/list in `scripts/verify_mcp.py` (currently 13) so
  the registry check passes.
- **Add / alias a GCP icon** → drop the SVG under `logo_icon_gcp/<service>/` and
  (if the folder name ≠ friendly name) add a `GCP_ICON_PATHS` entry + optional
  `_LABEL_PATTERNS` needle in `gcp_icons.py`. Add a `GCP_SERVICE_NAMES` entry so
  the label shows the right display name.
- **Fix a service display name** → edit `GCP_SERVICE_NAMES` (keyed by SVG folder
  stem) in `gcp_icons.py`. Behavior + impacted files are documented in
  `README.md` → "GCP service names beside every icon".
- **Change spacing / routing** → edit the layout constants above; re-verify edge
  routing on a busy diagram.
- **Restrict a service** → edit `policy/unavailable_services.md` (ban list +
  alternatives). The guardrail is enforced by the prompts (step 2a), not code.
- **Change the connector contract** → schema in
  `docs/connector-details-template.md`; generator is
  `scripts/generate_connector_details.py`; the in-canvas table is
  `tools/add_connector_table.py`.

## Test & verify

```bash
# unit tests
cd drawio-mcp-server && ../.venv/bin/python -m pytest -q

# server + diagram gate (self-bootstraps under the venv)
.venv/bin/python scripts/verify_mcp.py --diagram <FILE>.drawio

# ad-hoc end-to-end (build a diagram in-process)
#   from drawio_mcp_server.tools.create_diagram import create_diagram
#   from drawio_mcp_server.tools.add_node import add_node
#   cfg = ServerConfig(diagrams_dir=Path(tmp).resolve(), stories_dir=..., icons_dir=Path("logo_icon_gcp").resolve())
```

Use `.venv/bin/python` (project venv). Scripts self-bootstrap under it, so the
same command works on macOS / Linux / Windows.

## Gotchas

- **Stale Python after a code edit** is the #1 "my change didn't take effect".
  `pkill -f drawio_mcp_server` then Reload VS Code — see
  `Installation Guide/vscode-restart-formality.md`.
- **Duplicate `<name> 2.md` / `<name> 2.py` files** are macOS copy artifacts,
  not variants — safe to delete once you confirm the base file is a superset.
- **`ANTHROPIC_API_KEY`** enables LLM rewrites in the normalizer / connector
  generator; without it they fall back to a delegate-payload mode the
  conversational LLM completes. Both paths are supported.
