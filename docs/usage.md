# Usage

## One-time setup

1. Install Python 3.10+.
2. Install the [draw.io VS Code extension](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio)
   so you can preview `.drawio` files in-editor (optional but strongly recommended).
3. Install the MCP server:
   ```bash
   cd drawio-mcp-server
   python -m venv .venv
   source .venv/bin/activate           # on Windows: .venv\Scripts\activate
   pip install -e .
   ```
4. Reload VS Code. The server registered in [`.vscode/mcp.json`](../.vscode/mcp.json)
   will start automatically when Copilot Chat opens. If VS Code does not
   pick up your venv's `python`, edit `.vscode/mcp.json` and set
   `"command"` to the absolute path of `.venv/bin/python`.
5. In Copilot Chat, open the MCP servers panel and confirm `drawio` is connected.
   You should see **13 tools** available: `list_diagrams`, `read_diagram`,
   `read_diagram_summary`, `list_stories`, `read_story`, `create_diagram`,
   `add_container`, `add_node`, `add_edge`, `add_title`, `add_connector_table`,
   `update_node`, `remove_element`.

## Daily workflow

### 1. Drop the Jira story
Download the story from Jira (Export → Word, or copy the description into
a text file) and save it as `jira-stories/PROJ-123.txt` (or `.md`).

### 2. Decide create vs update

```text
@workspace use the prompt at prompts/update-diagram.md.
The story is jira-stories/DEMO-001.txt.
The diagram is diagrams/system.drawio.
```

or for a brand-new diagram:

```text
@workspace use the prompt at prompts/create-diagram.md.
The story is jira-stories/DEMO-001.txt.
Save the diagram as diagrams/demo-001.drawio.
```

Copilot will:
- read the story,
- summarize the existing diagram (if any),
- propose a plan,
- wait for your approval,
- apply the changes one tool call at a time.

### 3. Review

- Open the saved `.drawio` file in the draw.io VS Code extension to verify
  it visually.
- `git diff diagrams/` to see exactly what changed in XML form.

## Resetting / iterating

- To discard Copilot's changes before saving: just don't approve the plan.
- To revert after saving: `git checkout -- diagrams/<file>.drawio`.
- To start fresh: delete the file from `diagrams/` and ask Copilot to
  `create_diagram` again.

## Troubleshooting

**MCP server not connecting**
Check the VS Code Output panel → "MCP". If you see `ModuleNotFoundError:
No module named 'drawio_mcp_server'`, your venv is not active for the
launched process — set the absolute venv `python` path in
[`.vscode/mcp.json`](../.vscode/mcp.json).

**`No module named 'mcp'`**
Run `pip install -e .` again inside the active venv.

**"Diagram payload appears compressed"**
Open the `.drawio` file in draw.io desktop, go to *Extras → Edit Diagram*,
uncheck *Compressed*, save. Future writes from this server are always
uncompressed.

**Copilot is editing XML directly instead of using tools**
Re-paste the prompt template — it explicitly forbids hand-editing. If it
still happens, check that `.github/copilot-instructions.md` is being
loaded (VS Code setting `github.copilot.chat.codeGeneration.useInstructionFiles`
must be `true`).
