# Linux — Setup scripts

These scripts run on **Linux (any distro)**. They are written in POSIX
bash and assume you've already installed `python3` (>=3.10) and `git`
via your distro's package manager.

> If you are on **macOS**, use [../mac/README.md](../mac/README.md)
> instead — the macOS `setup.sh` is a true one-shot installer that
> also installs Homebrew, Python, Git, and (optionally) VS Code.
>
> If you are on **Windows**, use
> [../windows/README.md](../windows/README.md) instead.

---

## What's in this folder

| File | Run when… | What it does |
|---|---|---|
| `setup.sh` | First time, or after pulling new code | Creates the Python venv, installs the MCP server in editable mode, patches `.vscode/mcp.json` to point at the venv's Python, and ensures `.vscode/settings.json` has the required keys. Idempotent. |
| `verify.sh` | After `setup.sh`, or anytime you suspect the server is broken | Sends an MCP `initialize` + `tools/list` JSON-RPC probe and confirms all 13 expected tools are advertised. |
| `run-server.sh` | Debugging without VS Code | Launches the server in the foreground over stdio with the right env vars. Press **Ctrl+C** to stop. |
| `demo.sh` | First end-to-end test | Copies `examples/sample-jira-story.txt` to `jira-stories/DEMO-001.txt` so you can immediately try the create-diagram prompt. |
| `clean.sh` | Resetting to a clean slate | Removes the venv. Pass `--all` to also delete the demo story and any generated `*.drawio` files. |

---

## Prerequisites (one-time)

You need these installed **before** running `setup.sh`. The script will
fail fast with a clear message if any are missing.

### 1. Python 3.10 or newer

```bash
# macOS (Homebrew)
brew install python@3.12

# Debian / Ubuntu
sudo apt update && sudo apt install -y python3.12 python3.12-venv

# Fedora / RHEL
sudo dnf install -y python3.12

# Verify
python3 --version          # must print >= 3.10
```

### 2. Git

```bash
brew install git           # macOS
sudo apt install -y git    # Debian / Ubuntu
git --version
```

### 3. VS Code with Copilot

- Install VS Code: <https://code.visualstudio.com/>
- Inside VS Code → Extensions, install:
  - **GitHub Copilot** (`GitHub.copilot`)
  - **GitHub Copilot Chat** (`GitHub.copilot-chat`) — required for MCP
  - Optional: **Draw.io Integration** by hediet — preview `.drawio` files in-editor

Sign in to GitHub Copilot from the VS Code account menu.

---

## Execution sequence

Run from the **repo root**, not from inside `scripts/linux/`.

```bash
cd /path/to/architecture_building_ai_solution
```

### Step 1 — Make the scripts executable (first time only)

```bash
chmod +x scripts/linux/*.sh
```

After this you can call them as `./scripts/linux/setup.sh`. If you skip
this, just prefix every command with `bash`, e.g. `bash scripts/linux/setup.sh`.

### Step 2 — Run the setup

```bash
./scripts/linux/setup.sh
```

What it does, in order:

1. Detects your OS and picks the best available `python3.x` interpreter
   (≥ 3.10).
2. Creates `drawio-mcp-server/.venv` if it doesn't exist.
3. Upgrades `pip` inside the venv.
4. `pip install -e .` — installs the server in **editable** mode (so
   future code edits don't need a reinstall).
5. Patches `.vscode/mcp.json` so the `command` is the absolute path to
   the venv's Python — this avoids the most common failure mode of VS
   Code launching the wrong interpreter.
6. Ensures `.vscode/settings.json` has these three keys:
   - `files.associations: { "*.drawio": "xml" }`
   - `chat.mcp.access: "all"`
   - `github.copilot.chat.codeGeneration.useInstructionFiles: true`

**Expected output ends with:**

```
[OK] Setup complete.
Next steps:
  1. bash scripts/linux/verify.sh
  ...
```

If anything in this step fails, fix it before continuing — the rest of
the scripts assume the venv exists.

### Step 3 — Verify

```bash
./scripts/linux/verify.sh
```

This sends the proper MCP handshake (`initialize` →
`notifications/initialized` → `tools/list`) and checks all 13 expected
tools are advertised. Successful output looks like:

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

If you see fewer than 13, re-run `setup.sh` and look for `pip install`
errors above.

### Step 4 — Open in VS Code and reload

```bash
code "/path/to/architecture_building_ai_solution"
```

Then inside VS Code:

1. Press **⇧⌘P** (mac) / **Ctrl+Shift+P** (linux).
2. Run **Developer: Reload Window**.
3. Open Copilot Chat (chat icon in the side bar, or **⌃⌘I** /
   **Ctrl+Alt+I**).
4. Click the small **MCP servers / tools** indicator in the chat input.
5. Confirm `drawio` is listed as **connected** with **13 tools**.

### Step 5 — (Optional) Drop the demo story

```bash
./scripts/linux/demo.sh
```

This copies `examples/sample-jira-story.txt` to
`jira-stories/DEMO-001.txt` and prints the prompt to paste into Copilot
Chat:

```
@workspace Use the prompt at prompts/create-diagram.md.
The story is jira-stories/DEMO-001.txt.
Save the diagram as diagrams/demo-001.drawio.
```

`demo.sh` refuses to overwrite an existing `DEMO-001.txt` if its
contents differ from the sample — so it's safe to run repeatedly.

### Step 6 — (Debug only) Run the server outside VS Code

```bash
./scripts/linux/run-server.sh
```

Use this when you want to read raw stderr / tracebacks without VS Code
in the way. The process blocks waiting for JSON-RPC on stdin — that's
correct. **Ctrl+C** to stop.

### Step 7 — (Optional) Reset

To wipe the venv and start over:

```bash
./scripts/linux/clean.sh
```

To also remove the demo story and any generated diagrams:

```bash
./scripts/linux/clean.sh --all
```

`.gitkeep` files in `diagrams/` and `jira-stories/` are preserved.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Permission denied` when running `./scripts/linux/setup.sh` | You skipped Step 1. Run `chmod +x scripts/linux/*.sh` or invoke with `bash scripts/linux/setup.sh`. |
| `Python 3.10+ not found` from `setup.sh` | Install Python (see Prerequisites). On Ubuntu, the venv module is a separate package: `sudo apt install python3.12-venv`. |
| `setup.sh` succeeds but `verify.sh` says "no output" | The venv Python can't import the `mcp` SDK. Re-run `setup.sh`. If it still fails, run `./scripts/linux/run-server.sh` to see the traceback. |
| `verify.sh` reports < 13 tools | The package was partially installed. `./scripts/linux/clean.sh && ./scripts/linux/setup.sh`. |
| VS Code MCP panel still shows `drawio — failed` after `verify.sh` succeeds | You forgot **Developer: Reload Window**. VS Code reads `mcp.json` only at window load. |
| `bash: bad interpreter` errors | The scripts have CRLF line endings (e.g. cloned with Windows git settings). Run `sed -i '' 's/\r$//' scripts/linux/*.sh` on macOS or `sed -i 's/\r$//' scripts/linux/*.sh` on Linux. |
| macOS Gatekeeper blocks the venv `python3` | `xattr -d com.apple.quarantine drawio-mcp-server/.venv/bin/python`, or rerun `setup.sh` after the OS prompt. |

---

## Quick reference

```bash
# First-time setup (one command)
chmod +x scripts/linux/*.sh && ./scripts/linux/setup.sh && ./scripts/linux/verify.sh

# Re-run setup after pulling changes
./scripts/linux/setup.sh

# Reset everything
./scripts/linux/clean.sh --all && ./scripts/linux/setup.sh
```

For the daily user workflow once setup is done, see
[../../docs/execution.md](../../docs/execution.md).
