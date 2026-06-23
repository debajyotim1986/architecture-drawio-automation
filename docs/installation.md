# Installation guide

End-to-end installation, in the exact order to run things. Follow the
steps top-to-bottom on a fresh machine and you will end up with a working
`drawio` MCP server connected to GitHub Copilot in VS Code.

> Tested on macOS (zsh), Linux (bash), and Windows (PowerShell). Where the
> commands differ, both forms are shown.

---

## Step 1 — Install Python 3.10 or newer

The MCP server requires Python ≥ 3.10 (it uses modern type-hint syntax
and the official `mcp` SDK).

**macOS** (Homebrew):
```bash
brew install python@3.12
```

**Linux** (Debian/Ubuntu):
```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv
```

**Windows** (winget):
```powershell
winget install Python.Python.3.12
```

Verify:
```bash
python3 --version    # macOS / Linux
python --version     # Windows
```
You should see `Python 3.10.x` or higher.

---

## Step 2 — Install Git

Needed to clone this repo and to diff `.drawio` files after Copilot edits
them.

**macOS:** `brew install git`
**Linux:** `sudo apt install -y git`
**Windows:** `winget install Git.Git`

Verify: `git --version`.

---

## Step 3 — Install VS Code

The MCP server is designed to be launched by VS Code's Copilot Chat over
stdio. Other MCP-aware clients work too, but this guide assumes VS Code.

Download from <https://code.visualstudio.com/> or:
- **macOS:** `brew install --cask visual-studio-code`
- **Linux:** see distro-specific package or use the `.deb` from the site
- **Windows:** `winget install Microsoft.VisualStudioCode`

---

## Step 4 — Install the GitHub Copilot extensions in VS Code

Open VS Code, go to **Extensions** (⇧⌘X / Ctrl+Shift+X), and install:

1. **GitHub Copilot** (`GitHub.copilot`)
2. **GitHub Copilot Chat** (`GitHub.copilot-chat`) — required for MCP support

Sign in with a GitHub account that has Copilot access (Individual,
Business, or Enterprise).

---

## Step 5 — Install the draw.io VS Code extension

Optional but strongly recommended — it lets you preview `.drawio` files
directly in the editor after Copilot updates them.

In VS Code Extensions, install:
- **Draw.io Integration** by `hediet` (`hediet.vscode-drawio`)

---

## Step 6 — Clone this repository

```bash
cd ~/Projects                                     # or wherever you keep code
git clone <your-fork-or-this-repo-url> architecture_building_ai_solution
cd architecture_building_ai_solution
```

If you already have the project locally, just `cd` into it.

---

## Step 7 — Create a Python virtual environment for the MCP server

Isolating the server's dependencies in a venv keeps your global Python
clean and pins the `mcp` and `pydantic` versions to this project.

```bash
cd drawio-mcp-server
python3 -m venv .venv             # macOS / Linux
# python -m venv .venv            # Windows
```

Activate the venv (you must do this every new terminal session, or set
the absolute python path in `.vscode/mcp.json` — see Step 10):

**macOS / Linux:**
```bash
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

Your shell prompt should now show `(.venv)` at the start.

---

## Step 8 — Install the MCP server in editable mode

From inside `drawio-mcp-server/` with the venv active:

```bash
pip install --upgrade pip
pip install -e .
```

This installs:
- `mcp` — the official Python MCP SDK (used by `server.py`)
- `pydantic` — used by `types.py` for the `Diagram` / `DiagramNode` /
  `DiagramEdge` models
- the `drawio_mcp_server` package itself, in editable mode (so code edits
  take effect on the next server restart without reinstalling)
- the `drawio-mcp-server` console script

Optional dev dependencies (`pytest`):
```bash
pip install -e ".[dev]"
```

---

## Step 9 — Verify the server can start

Still inside the activated venv:

```bash
python -m drawio_mcp_server
```

You should see the line `[drawio-mcp] connected. diagrams=... stories=...`
on **stderr** and then the process will block waiting for MCP input on
stdin — this is correct. Press **Ctrl+C** to exit.

If you see `ModuleNotFoundError: No module named 'mcp'` or
`'drawio_mcp_server'`, repeat Step 8 inside the active venv.

---

## Step 10 — Point VS Code at the venv's Python (if needed)

VS Code may launch a different `python` than the one in your venv. The
[`.vscode/mcp.json`](../.vscode/mcp.json) file sets `PYTHONPATH` to the
package's `src/` so it usually works without a venv at all — **but** the
`mcp` and `pydantic` dependencies must be importable.

The cleanest fix is to point `mcp.json` at the venv's interpreter
explicitly. Edit [`.vscode/mcp.json`](../.vscode/mcp.json) and replace
`"command": "python"` with one of:

**macOS / Linux:**
```json
"command": "${workspaceFolder}/drawio-mcp-server/.venv/bin/python"
```

**Windows:**
```json
"command": "${workspaceFolder}/drawio-mcp-server/.venv/Scripts/python.exe"
```

Save the file.

---

## Step 11 — Reload VS Code and confirm the MCP server is connected

1. Open the workspace folder (`architecture_building_ai_solution`) in VS Code.
2. Reload the window: ⇧⌘P / Ctrl+Shift+P → **Developer: Reload Window**.
3. Open Copilot Chat (the chat icon in the side bar).
4. Click the **MCP servers** indicator (in the chat input area). You
   should see `drawio` listed as **connected**, and clicking it should
   reveal **13 tools**: `list_diagrams`, `read_diagram`,
   `read_diagram_summary`, `list_stories`, `read_story`,
   `create_diagram`, `add_container`, `add_node`, `add_edge`,
   `add_title`, `add_connector_table`, `update_node`, `remove_element`.

If the server shows as failed, open **View → Output → MCP** (or
**View → Output** and pick **MCP** from the dropdown) to see why.
The most common cause is the wrong `python` path — re-do Step 10.

---

## Step 12 — Drop a Jira story and try the workflow

1. Use the bundled demo script (which copies
   [`examples/sample-jira-story.txt`](../examples/sample-jira-story.txt)
   to `jira-stories/DEMO-001.txt` — we deliberately avoid `PROJ-123.txt`
   because that file is the canonical worked-example story the docs and
   prompts point at):
   ```bash
   ./scripts/linux/demo.sh    # or scripts/mac/demo.sh, or scripts\windows\demo.ps1
   ```
2. In Copilot Chat, paste:
   ```text
   @workspace use the prompt at prompts/create-diagram.md.
   The story is jira-stories/DEMO-001.txt.
   Save the diagram as diagrams/demo-001.drawio.
   ```
3. Approve Copilot's plan when it asks. It will then call the MCP tools
   one at a time to build the diagram.
4. Open the resulting `diagrams/demo-001.drawio` file — the
   draw.io extension (Step 5) renders it visually.

---

## Step 13 — (Optional) Run the test suite

If you installed the dev extras in Step 8:

```bash
cd drawio-mcp-server
source .venv/bin/activate
pytest
```

The bundled `tests/test_parser.py` is currently a placeholder; replace it
with real cases as the parser hardens.

---

## MCP server command cheat sheet

A grouped reference of every command you'll likely run while working with
the server. Run these from the **server folder**
(`architecture_building_ai_solution/drawio-mcp-server/`) with the venv activated
unless noted otherwise.

### Activate / deactivate the venv

```bash
# Activate (run once per terminal session)
source .venv/bin/activate                          # macOS / Linux
.\.venv\Scripts\Activate.ps1                       # Windows PowerShell
.\.venv\Scripts\activate.bat                       # Windows cmd.exe

# Deactivate (return to system Python)
deactivate

# Confirm which Python is active
which python                                       # macOS / Linux
where python                                       # Windows
python -c "import sys; print(sys.executable)"      # cross-platform
```

### Install / reinstall / update the server package

```bash
# First-time install (editable, reads pyproject.toml from `.`)
pip install -e .

# With dev extras (adds pytest)
pip install -e ".[dev]"

# Reinstall (after a tooling glitch — does not re-resolve deps)
pip install -e . --force-reinstall --no-deps

# Full clean reinstall (drops + recreates the venv)
deactivate && rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate && pip install -U pip && pip install -e ".[dev]"

# Upgrade just the MCP SDK
pip install -U mcp

# Upgrade everything that's outdated
pip list --outdated
pip install -U mcp pydantic
```

### Inspect what's installed

```bash
# Show this package's metadata + install location
pip show drawio-mcp-server

# Confirm it's in editable mode (look for "Editable project location:")
pip show drawio-mcp-server | grep -i editable

# List every file the package owns
pip show -f drawio-mcp-server

# Full dependency tree of the venv
pip list
pip list --format=freeze > requirements.lock        # snapshot for reproducibility

# Where does Python find the package?
python -c "import drawio_mcp_server, pathlib; print(pathlib.Path(drawio_mcp_server.__file__).parent)"

# Where does the console script live?
which drawio-mcp-server                             # macOS / Linux
where drawio-mcp-server                             # Windows
```

### Run the server manually (smoke test)

The server speaks MCP over stdio — running it standalone just blocks
waiting for input. That's normal. Use this to confirm it boots without
import errors.

```bash
# Module form (always works)
python -m drawio_mcp_server

# Console-script form (after `pip install -e .`)
drawio-mcp-server

# Override the diagrams / stories folders for a one-off run
DRAWIO_DIAGRAMS_DIR=/tmp/my-diagrams \
DRAWIO_STORIES_DIR=/tmp/my-stories \
python -m drawio_mcp_server

# Send a fake `tools/list` request and exit (sanity-check the wire protocol)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python -m drawio_mcp_server
```

Press **Ctrl+C** to stop a manually-launched server.

### Validate the package & code

```bash
# Quick import check — fails fast if any module has a syntax error
python -c "import drawio_mcp_server; print(drawio_mcp_server.__version__)"

# Bytecode-compile every file (catches syntax errors across the package)
python -m compileall -q src/drawio_mcp_server

# Run the test suite
pytest                                              # all tests
pytest -q                                           # quiet
pytest tests/test_parser.py -k roundtrip -v         # one test, verbose
pytest --maxfail=1 -x                               # stop on first failure

# (Optional) static checks if you add them later
python -m pyflakes src/drawio_mcp_server
python -m mypy src/drawio_mcp_server
```

### Manage the server lifecycle inside VS Code

These run from the VS Code command palette
(**⇧⌘P** / **Ctrl+Shift+P**), not the shell:

| What you want | Command-palette entry |
|---|---|
| Restart the `drawio` MCP server | `MCP: Restart Server` → pick `drawio` |
| Stop / disable it | `MCP: Stop Server` → pick `drawio` |
| Re-read `.vscode/mcp.json` | `Developer: Reload Window` |
| Watch its stderr live | `View: Toggle Output` → choose `MCP` from the dropdown |
| Re-list available MCP tools | `MCP: List Servers` |

### Debug a misbehaving server

```bash
# 1. Tail the live log written by VS Code (macOS default location)
tail -f "$HOME/Library/Application Support/Code/logs/"*/exthost*/MCP*

# 2. Run the server with verbose Python tracebacks visible
PYTHONFAULTHANDLER=1 python -m drawio_mcp_server

# 3. Print every import path Python is searching
python -c "import sys; print('\n'.join(sys.path))"

# 4. Confirm the venv binary VS Code is actually launching
cat .vscode/mcp.json | grep -A1 command            # from workspace root

# 5. Re-test outside VS Code by piping a single tool call
python - <<'PY'
import asyncio, json
from drawio_mcp_server.tools import dispatch_tool
from drawio_mcp_server.util.config import resolve_config
print(asyncio.run(dispatch_tool("list_diagrams", {}, resolve_config())))
PY
```

### Manage diagrams and stories from the shell

```bash
# From the workspace root:
ls diagrams/                                        # what diagrams exist
ls jira-stories/                                    # what stories are queued
cat jira-stories/PROJ-123.txt                       # peek at a story
git diff diagrams/                                  # what Copilot just changed
git checkout -- diagrams/system.drawio              # discard Copilot's edits
rm diagrams/demo-001.drawio               # start over for one diagram
```

### Uninstall / remove

```bash
# Remove just the package, keep the venv and other deps
pip uninstall drawio-mcp-server

# Nuke the venv entirely (safest reset)
deactivate && rm -rf .venv
```

### One-shot recipes

```bash
# "It worked yesterday and broke today" — full reset, from server folder
deactivate 2>/dev/null; rm -rf .venv && python3 -m venv .venv \
  && source .venv/bin/activate && pip install -U pip && pip install -e ".[dev]" \
  && python -m drawio_mcp_server <<< '' ; echo "boot OK"

# "I just edited a tool file, restart the server"
#   → in VS Code: ⇧⌘P → MCP: Restart Server → drawio
#   (no re-install needed because of editable mode)

# "Show me what tools the server advertises right now"
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python -m drawio_mcp_server | python -m json.tool
```

---

## Troubleshooting cheat sheet

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'mcp'` | Re-run `pip install -e .` inside the activated venv. |
| `ModuleNotFoundError: No module named 'drawio_mcp_server'` | Same as above; or check `PYTHONPATH` in `.vscode/mcp.json`. |
| MCP panel shows `drawio` as failed | Open **Output → MCP**, fix the python path in `.vscode/mcp.json` (Step 10). |
| `Diagram payload appears compressed/encoded` | Open the `.drawio` file in draw.io desktop → *Extras → Edit Diagram* → uncheck *Compressed* → save. |
| Copilot edits XML directly instead of calling tools | Re-paste the prompt from `prompts/`, and verify `github.copilot.chat.codeGeneration.useInstructionFiles` is `true`. |
| `Refusing path outside diagrams root` | Caller passed a path with `..` in it; use a plain filename. |

---

## What "done" looks like

You're fully set up when **all** of these are true:

- `python --version` ≥ 3.10 inside the activated venv.
- `pip show drawio-mcp-server` shows the package as installed.
- VS Code Copilot Chat lists `drawio` as **connected** with 13 tools.
- Running the Step 12 walkthrough produces a new `.drawio` file inside
  `diagrams/` and the draw.io extension renders it without errors.
