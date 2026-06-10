# Windows — Setup scripts

PowerShell scripts that install and verify the drawio MCP server on
Windows 10 / 11. Tested on PowerShell 5.1 (built into Windows) and
PowerShell 7+.

> If you are on **Linux** or **macOS**, stop here and use
> [../linux/README.md](../linux/README.md) instead.

---

## What's in this folder

| File | Run when… | What it does |
|---|---|---|
| `setup.ps1` | First time, or after pulling new code | Creates the Python venv at `drawio-mcp-server\.venv`, installs the MCP server in editable mode, patches `.vscode\mcp.json` to point at the venv's `python.exe`, and ensures `.vscode\settings.json` has the required keys. Idempotent. |
| `verify.ps1` | After `setup.ps1`, or anytime you suspect the server is broken | Sends an MCP `initialize` + `tools/list` JSON-RPC probe and confirms all 13 expected tools are advertised. |
| `run-server.ps1` | Debugging without VS Code | Launches the server in the foreground over stdio with the right env vars. Press **Ctrl+C** to stop. |
| `demo.ps1` | First end-to-end test | Copies `examples\sample-jira-story.txt` to `jira-stories\DEMO-001.txt` so you can immediately try the create-diagram prompt. |
| `clean.ps1` | Resetting to a clean slate | Removes the venv. Pass `-All` to also delete the demo story and any generated `*.drawio` files. |

---

## Prerequisites (one-time)

You need these installed **before** running `setup.ps1`. The script will
fail fast with a clear message if any are missing.

### 1. Python 3.10 or newer

```powershell
winget install Python.Python.3.12
# Close and re-open PowerShell so PATH picks up python.exe
python --version          # must print >= 3.10
```

If `winget` is not available, download Python from
<https://www.python.org/downloads/> and during install **tick "Add
python.exe to PATH"**.

### 2. Git

```powershell
winget install Git.Git
git --version
```

### 3. VS Code with Copilot

```powershell
winget install Microsoft.VisualStudioCode
```

Inside VS Code → Extensions, install:

- **GitHub Copilot** (`GitHub.copilot`)
- **GitHub Copilot Chat** (`GitHub.copilot-chat`) — required for MCP
- Optional: **Draw.io Integration** by hediet — preview `.drawio`
  files in-editor

Sign in to GitHub Copilot from the VS Code account menu.

### 4. PowerShell execution policy (one-time)

By default, Windows blocks unsigned local scripts. You have two options.

**Option A — bypass per-invocation (no system change):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
```

**Option B — allow local scripts permanently for the current user:**

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

After Option B you can run scripts directly: `.\scripts\windows\setup.ps1`.

---

## Execution sequence

Open **PowerShell** (not "Command Prompt"). Run from the **repo root**:

```powershell
cd C:\path\to\architecture_building_ai_solution
```

### Step 1 — Run the setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
```

What it does, in order:

1. Picks the best Python interpreter from this list, preferring newer
   versions: `py -3.12`, `py -3.11`, `py -3.10`, `py -3`, `python`,
   `python3`. Requires ≥ 3.10.
2. Creates `drawio-mcp-server\.venv` if it doesn't exist.
3. Upgrades `pip` inside the venv.
4. `pip install -e .` — installs the server in **editable** mode (so
   future code edits don't need a reinstall).
5. Patches `.vscode\mcp.json` so the `command` is the absolute path to
   the venv's `python.exe` — this avoids the most common failure mode
   of VS Code launching the wrong interpreter.
6. Ensures `.vscode\settings.json` has these three keys:
   - `files.associations: { "*.drawio": "xml" }`
   - `chat.mcp.access: "all"`
   - `github.copilot.chat.codeGeneration.useInstructionFiles: true`

**Expected output ends with:**

```
[OK] Setup complete.
Next steps:
  1. powershell -ExecutionPolicy Bypass -File scripts\windows\verify.ps1
  ...
```

If anything in this step fails, fix it before continuing — the rest of
the scripts assume the venv exists.

#### Offline / blocked-network install

If your network blocks PyPI, the repo can ship a pre-built **`wheels\`**
folder (a wheelhouse — see [`wheels\README.md`](../../wheels/README.md)).
When `setup.ps1` sees a populated `wheels\` folder it switches to offline
mode automatically — you'll see `[OK] Offline wheelhouse detected` — and:

- installs the package **and** the `anthropic` SDK plus every dependency
  from `wheels\` with `--no-index` (no PyPI contact);
- requires the **exact** Python version the wheelhouse was built for
  (e.g. 3.12), rather than "newest wins";
- if that Python is missing, tries `winget install Python.Python.3.12`
  automatically (winget uses Microsoft's CDN, which is usually reachable
  even when PyPI is blocked).

No extra flags are needed — just run `setup.ps1` as normal.

### Step 2 — Verify

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\verify.ps1
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

If you see fewer than 13, re-run `setup.ps1` and look for `pip install`
errors above.

### Step 3 — Open in VS Code and reload

```powershell
code "C:\path\to\architecture_building_ai_solution"
```

Then inside VS Code:

1. Press **Ctrl+Shift+P**.
2. Run **Developer: Reload Window**.
3. Open Copilot Chat (chat icon in the side bar, or **Ctrl+Alt+I**).
4. Click the small **MCP servers / tools** indicator in the chat input.
5. Confirm `drawio` is listed as **connected** with **13 tools**.

### Step 4 — (Optional) Drop the demo story

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\demo.ps1
```

This copies `examples\sample-jira-story.txt` to
`jira-stories\PROJ-123.txt` and prints the prompt to paste into Copilot
Chat:

```
@workspace Use the prompt at prompts/create-diagram.md.
The story is jira-stories/DEMO-001.txt.
Save the diagram as diagrams/demo-001.drawio.
```

`demo.ps1` refuses to overwrite an existing `DEMO-001.txt` if its
contents differ from the sample — safe to run repeatedly.

### Step 5 — (Debug only) Run the server outside VS Code

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run-server.ps1
```

Use this when you want to read raw stderr / tracebacks without VS Code
in the way. The process blocks waiting for JSON-RPC on stdin — that's
correct. **Ctrl+C** to stop.

### Step 6 — (Optional) Reset

To wipe the venv and start over:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\clean.ps1
```

To also remove the demo story and any generated diagrams:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\clean.ps1 -All
```

`.gitkeep` files in `diagrams\` and `jira-stories\` are preserved.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `cannot be loaded because running scripts is disabled` | Use `-ExecutionPolicy Bypass` (Option A in Prerequisites) or run the `Set-ExecutionPolicy` command (Option B). |
| `Python 3.10+ not found` from `setup.ps1` | Install Python via `winget install Python.Python.3.12` and **re-open PowerShell** so PATH refreshes. |
| `python : The term 'python' is not recognized` | Python isn't on PATH. Reinstall and tick "Add python.exe to PATH", or use `py` (the official launcher). |
| `setup.ps1` succeeds but `verify.ps1` says "no output" | The venv Python can't import the `mcp` SDK. Re-run `setup.ps1`. If it still fails, run `run-server.ps1` to see the traceback. |
| `verify.ps1` reports < 13 tools | The package was partially installed. Run `clean.ps1` then `setup.ps1` again. |
| VS Code MCP panel still shows `drawio — failed` after `verify.ps1` succeeds | You forgot **Developer: Reload Window**. VS Code reads `mcp.json` only at window load. |
| Long-path errors during `pip install` | Enable Win32 long paths: <https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation>. |
| `'cmd' is not recognized` from inside `setup.ps1` | You're running on PowerShell Core on a non-Windows host. These scripts are Windows-only — use the Linux folder instead. |
| Anti-virus blocks the venv `python.exe` | Whitelist `drawio-mcp-server\.venv\Scripts\python.exe`. |

---

## Quick reference

```powershell
# First-time setup (one line)
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1; `
powershell -ExecutionPolicy Bypass -File scripts\windows\verify.ps1

# Re-run setup after pulling changes
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1

# Reset everything
powershell -ExecutionPolicy Bypass -File scripts\windows\clean.ps1 -All; `
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
```

For the daily user workflow once setup is done, see
[..\..\docs\execution.md](../../docs/execution.md).
