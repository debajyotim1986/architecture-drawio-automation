# VS Code restart formality — run before every diagram prompt

VS Code's **MCP: Restart Server** command does not reliably kill the child
Python process. When the old process survives, Copilot keeps talking to a
server with **stale Python imports in RAM** — so any code change you made
in `drawio-mcp-server/src/` is silently ignored and your new diagrams ship
with the old defaults (cramped grid, labels stamped on top of the arrow).

Run the following checklist **every time** you reload VS Code, and again
before you run a `prompts/create-diagram.md` prompt if you recently
touched the server code.

---

## 1. Verify no stale server is alive

From the repo root in a regular terminal (not the VS Code one):

```bash
pgrep -fl drawio_mcp_server
```

Expected output: **empty** (one blank line, exit code 1 — that's success).

If you see a PID, the old server is still running. Kill it:

```bash
pkill -f drawio_mcp_server
```

Re-run `pgrep` to confirm it's gone.

> Why a separate terminal? The VS Code integrated terminal is fine too,
> but the MCP server is spawned by VS Code itself — not by any terminal
> session — so killing it from any shell works identically.

---

## 2. Reload the VS Code window

Inside VS Code:

**⇧⌘P** → `Developer: Reload Window`

This forces VS Code to drop its MCP client connection. The next Copilot
tool call will spawn a fresh server process that reads the current code
on disk.

---

## 3. (Optional) Smoke-test the new server

From the repo root:

```bash
./scripts/mac/verify.sh
```

Expected:

```
Tools advertised: 13
  list_diagrams
  read_diagram
  read_diagram_summary
  create_diagram
  add_title
  add_container
  add_node
  add_edge
  add_connector_table
  update_node
  remove_element
  list_stories
  read_story
[OK] All 13 expected tools are present.
```

If this fails, the server itself is broken — fix that before going near
Copilot.

---

## 4. Generate the diagram

Open Copilot Chat and run your prompt as usual, e.g.

```
@workspace Use the prompt at prompts/create-diagram.md.
The story is jira-stories/DEMO-001.txt.
```

---

## 5. Sanity-check the generated `.drawio` file

Open the new file and confirm these three markers — they prove the new
code wrote it. If any is missing, the server didn't actually restart
(go back to step 1).

| Marker | Where | Expected value |
|---|---|---|
| Page width | Near the top, in `<mxGraphModel ... >` | `pageWidth="1500"` (not `1169`) |
| Edge style | Every `<mxCell ... edge="1" ...>` | `style="...;verticalAlign=bottom;labelBackgroundColor=#ffffff;"` |
| Label offset | Every **labeled** edge's geometry | `<mxPoint x="0" y="-22" as="offset" />` inside the `<mxGeometry>` |

A quick grep does the job:

```bash
grep -c 'pageWidth="1500"' diagrams/<your-new-file>.drawio   # → 1
grep -c 'verticalAlign=bottom' diagrams/<your-new-file>.drawio  # → one per edge
grep -c '"offset"' diagrams/<your-new-file>.drawio  # → one per labeled edge
```

If all three numbers are non-zero, labels render above the connector
line — every time.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| New diagram still has `pageWidth="1169"` | Stale server survived `Reload Window` | `pkill -f drawio_mcp_server`, then Reload Window again |
| Edge labels still overlap the arrow line | Same as above — old code in RAM | Same fix |
| `pgrep -fl drawio_mcp_server` shows two PIDs | VS Code spawned a second instance | Kill both: `pkill -9 -f drawio_mcp_server`, then Reload Window |
| `verify.sh` reports < 13 tools | Code change broke the server | `./scripts/mac/clean.sh && ./scripts/mac/setup.sh` |
| Diagram exists but the file on disk is unchanged | Diagram was created by the **old** server before restart | Delete it and re-run the prompt — existing node positions are baked into the file and won't auto-update |
