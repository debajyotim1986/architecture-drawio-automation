# macOS — Setup scripts

These scripts are tailored for **macOS** (Apple Silicon and Intel). They go a
step further than the Linux scripts: a single `setup.sh` will install
**every** prerequisite (Homebrew, Python, Git, optionally VS Code) **and**
the MCP server, so you can go from a clean Mac to a working Copilot/MCP
setup with one command.

> If you are on **Linux**, use [../linux/](../linux/) instead.
> If you are on **Windows**, use [../windows/](../windows/) instead.

---

## What's in this folder

| File | Run when… | What it does |
|---|---|---|
| `setup.sh` | First time, or after pulling new code | One-shot installer: installs Homebrew (if missing), Python 3.12, Git, optionally VS Code; creates the venv; installs the MCP server in editable mode; patches `.vscode/mcp.json` and `.vscode/settings.json`. Idempotent. |
| `verify.sh` | After `setup.sh`, or anytime you suspect the server is broken | Sends an MCP `initialize` + `tools/list` JSON-RPC probe and confirms all 13 expected tools are advertised. |
| `run-server.sh` | Debugging without VS Code | Launches the server in the foreground over stdio with the right env vars. Press **Ctrl+C** to stop. |
| `demo.sh` | First end-to-end test | Copies `examples/sample-jira-story.txt` to `jira-stories/DEMO-001.txt` (avoids clobbering `PROJ-123.txt` which is the normalizer's reference template). |
| `clean.sh` | Resetting to a clean slate | Removes the venv. Pass `--all` to also delete the demo story and any generated `*.drawio` files. |

---

## One-command install

```bash
cd /path/to/architecture_building_ai_solution
chmod +x scripts/mac/*.sh
./scripts/mac/setup.sh
```

That single command does **all** of the following, in order:

1. Installs **Homebrew** if it isn't already present.
2. Installs **Python 3.12** if no `python3.10+` is on PATH.
3. Installs **Git** if missing.
4. Installs **Visual Studio Code** (cask) if neither `code` is on PATH nor
   the app is in `/Applications`.
5. Creates the project venv at `drawio-mcp-server/.venv`.
6. Upgrades pip and `pip install -e drawio-mcp-server` — this is the
   **MCP server install**.
7. Patches `.vscode/mcp.json` so VS Code launches the venv's Python.
8. Ensures `.vscode/settings.json` has the keys MCP/Copilot need:
   - `files.associations: { "*.drawio": "xml" }`
   - `chat.mcp.access: "all"`
   - `github.copilot.chat.codeGeneration.useInstructionFiles: true`

It is safe to re-run.

### Flags

| Flag | Effect |
|---|---|
| `--skip-prereqs` | Don't try to install Homebrew, Python, Git, or VS Code. Use this if you manage those yourself (e.g. `pyenv`, `asdf`). |
| `--skip-vscode` | Install Homebrew/Python/Git but **don't** install VS Code via cask. |
| `--with-extensions` | After VS Code is installed, also `code --install-extension` the **GitHub Copilot** and **GitHub Copilot Chat** extensions. Requires the `code` CLI. |
| `--yes` / `-y` | Non-interactive: assume "yes" for any confirmation prompt (Homebrew install, VS Code install). |

Examples:

```bash
# Fully automated, end-to-end, including Copilot extensions
./scripts/mac/setup.sh --with-extensions --yes

# I already have Python via pyenv; just do the venv + MCP install
./scripts/mac/setup.sh --skip-prereqs

# Install everything except VS Code (I'll do that myself)
./scripts/mac/setup.sh --skip-vscode
```

---

## Manual prerequisites (only if you opt out)

If you pass `--skip-prereqs`, you must have these installed yourself:

- **Python 3.10+** — `brew install python@3.12` or via `pyenv` / `asdf`
- **Git** — `brew install git` (or use the Xcode Command Line Tools version)
- **VS Code** with the **GitHub Copilot** + **GitHub Copilot Chat**
  extensions and a Copilot subscription. Install from
  <https://code.visualstudio.com/> if you don't have it.

---

## Execution sequence

Run from the **repo root**, not from inside `scripts/mac/`.

### Step 1 — Make scripts executable (first time only)

```bash
chmod +x scripts/mac/*.sh
```

### Step 2 — Run the one-shot setup

```bash
./scripts/mac/setup.sh
```

You'll see colored `==>` step lines and `[OK]` confirmations. Successful
output ends with:

```
[OK] Setup complete.
Next steps:
  1. bash scripts/mac/verify.sh
  ...
```

### Step 3 — Verify

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

### Step 4 — Open in VS Code and reload

```bash
code "$(pwd)"
```

If `code` isn't on your PATH, open VS Code, press **⇧⌘P**, run
**Shell Command: Install 'code' command in PATH**, then re-run the line
above.

Inside VS Code:

1. **⇧⌘P** → **Developer: Reload Window**.
2. Open Copilot Chat (chat icon in the side bar, or **⌃⌘I**).
3. Click the small **MCP servers / tools** indicator in the chat input.
4. Confirm `drawio` is listed as **connected** with **13 tools**.

### Step 5 — (Optional) Drop the demo story

```bash
./scripts/mac/demo.sh
```

Then in Copilot Chat, paste:

```
@workspace Use the prompt at prompts/create-diagram.md.
The story is jira-stories/DEMO-001.txt.
Save the diagram as diagrams/demo-001.drawio.
```

### Step 6 — (Debug only) Run the server outside VS Code

```bash
./scripts/mac/run-server.sh
```

Server blocks waiting for JSON-RPC on stdin — that's correct. **Ctrl+C** to stop.

### Step 7 — (Optional) Reset

```bash
./scripts/mac/clean.sh           # venv only
./scripts/mac/clean.sh --all     # venv + demo story + generated diagrams
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Permission denied` on `./scripts/mac/setup.sh` | `chmod +x scripts/mac/*.sh`, or invoke with `bash scripts/mac/setup.sh`. |
| `command not found: brew` after install | Open a new terminal — Homebrew adds itself to `~/.zprofile` but the current shell doesn't see it. Or `eval "$(/opt/homebrew/bin/brew shellenv)"`. |
| Apple Silicon: `Bad CPU type in executable` from Python | You picked an Intel Python under Rosetta. Run `arch -arm64 brew install python@3.12` then re-run setup. |
| `setup.sh` succeeds but `verify.sh` says "no output" | `./scripts/mac/run-server.sh` to see the import traceback; usually means the editable install was interrupted. Re-run setup. |
| `verify.sh` reports < 13 tools | `./scripts/mac/clean.sh && ./scripts/mac/setup.sh`. |
| VS Code MCP panel still shows `drawio — failed` after `verify.sh` succeeds | You forgot **Developer: Reload Window**. VS Code reads `mcp.json` only at window load. |
| Gatekeeper blocks the venv `python3` ("cannot be opened because the developer cannot be verified") | `setup.sh` already runs `xattr -dr com.apple.quarantine` on the venv — re-run it, or open System Settings → Privacy & Security → "Allow anyway". |
| `code` CLI not found | In VS Code: **⇧⌘P** → **Shell Command: Install 'code' command in PATH**. |
| Behind a corporate proxy and Homebrew install hangs | Set `HTTPS_PROXY` / `HTTP_PROXY` before running. |

---

## Quick reference

```bash
# First-time, fully automated (incl. Copilot extensions)
chmod +x scripts/mac/*.sh && ./scripts/mac/setup.sh --with-extensions --yes && ./scripts/mac/verify.sh

# Re-run after pulling changes
./scripts/mac/setup.sh

# Reset everything
./scripts/mac/clean.sh --all && ./scripts/mac/setup.sh
```

For the daily user workflow once setup is done, see
[../../docs/execution.md](../../docs/execution.md).
