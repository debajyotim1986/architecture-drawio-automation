# Setup scripts

Automated installers for the AI Atlassian Copilot project. Run these
instead of doing the [docs/installation.md](../docs/installation.md)
steps by hand.

## Pick your folder

| OS | Folder | Notes |
|---|---|---|
| **Linux** (any distro) | [linux/](linux/) | Bash scripts. Tested on Ubuntu/Debian. |
| **macOS** | [mac/](mac/) | Bash scripts tailored for macOS. `setup.sh` is a true one-shot installer: Homebrew + Python + Git + (optionally) VS Code + the MCP server, all in one command. Apple Silicon and Intel both supported. |
| **Windows** | [windows/](windows/) | PowerShell scripts. Run from PowerShell 5.1+ (built into Windows 10/11). |

The macOS scripts are functionally equivalent to the Linux ones for the
day-to-day flow (verify / run / demo / clean), but the macOS `setup.sh`
will additionally install missing system prerequisites via Homebrew —
the Linux scripts assume you've installed `python3` yourself.

---

## What each script does

| Script | Linux | macOS | Windows | Purpose |
|---|---|---|---|---|
| **Setup** | `linux/setup.sh` | `mac/setup.sh` | `windows/setup.ps1` | One-shot end-to-end install: creates the venv, installs the package in editable mode, points `.vscode/mcp.json` at the venv's Python. Safe to re-run. The macOS variant additionally installs Homebrew, Python, Git, and (optionally) VS Code if missing. |
| **Verify** | `linux/verify.sh` | `mac/verify.sh` | `windows/verify.ps1` | Sanity check after setup. Sends a `tools/list` JSON-RPC probe to the server and confirms all 13 tools are present. |
| **Run** | `linux/run-server.sh` | `mac/run-server.sh` | `windows/run-server.ps1` | Launches the server in the foreground (handy when debugging without VS Code). Press Ctrl+C to stop. |
| **Demo** | `linux/demo.sh` | `mac/demo.sh` | `windows/demo.ps1` | Drops the bundled `examples/sample-jira-story.txt` into `jira-stories/DEMO-001.txt` so you can try the create-diagram flow immediately. |
| **Clean** | `linux/clean.sh` | `mac/clean.sh` | `windows/clean.ps1` | Removes the venv (and optionally the demo story / generated diagrams) to reset to a fresh state. |
| **Normalize** | `linux/normalize.sh` | `mac/normalize.sh` | `windows/normalize.ps1` | Thin wrapper around the cross-platform `scripts/normalize_jira_story.py`. Converts a plain-English Jira note into the canonical surgical format the create / update prompts expect, writing `<KEY>-surgical.txt` alongside the input. See [normalizer section](#jira-story-normalizer) below. |
| **Verify (cross-platform)** | `scripts/verify_mcp.py` | `scripts/verify_mcp.py` | `scripts/verify_mcp.py` | Pre-finalization gate run by the diagram prompts before saving. Confirms the MCP server's tool registry is healthy AND (with `--diagram <file>`) that the diagram is structurally sound — no dangling edges, no duplicate node labels, and every GCP-iconable node uses its official icon. Self-bootstraps under the venv; same command works on every OS. See [verify section](#diagram-verifier) below. The per-OS `verify.sh` / `verify.ps1` scripts remain available for post-setup server-health probing via JSON-RPC. |

---

## Jira story normalizer

`scripts/normalize_jira_story.py` is **cross-platform** (pure Python,
uses `pathlib`, no shell-specific code). It lives at the top of
`scripts/`, **not** under any OS folder.

The script **self-bootstraps**: on first import it detects the host
OS via `sys.platform`, locates the project venv Python
(`.venv/bin/python` on macOS/Linux, `.venv\Scripts\python.exe` on
Windows) and re-execs itself under that interpreter. This means a
single command works on every OS regardless of which Python the user
invokes it with:

    python scripts/normalize_jira_story.py jira-stories/PROJ-124.txt

The per-OS wrappers (`mac/normalize.sh`, `linux/normalize.sh`,
`windows/normalize.ps1`) are still available as a fallback for users
who prefer them, but you don't need to pick one based on your OS — the
bootstrap inside the script handles that automatically.

### How it integrates with the prompts

When you run `prompts/create-diagram.md` or `prompts/update-diagram.md`
in Copilot Chat, step 0 invokes the normalizer. It writes a sibling
file `jira-stories/<KEY>-surgical.txt` (the original is left
untouched), and subsequent `read_story` calls consume the surgical
file. See the prompt files for the exact decision tree.

### Setup

The relevant setup script installs the `[normalizer]` extra
automatically, which pulls in the `anthropic` SDK used for LLM rewrites
when the input note isn't already canonical.

| OS | Command |
|---|---|
| macOS | `./scripts/mac/setup.sh` |
| Linux | `bash scripts/linux/setup.sh` |
| Windows | `pwsh scripts\windows\setup.ps1` |

To enable LLM rewrites set `ANTHROPIC_API_KEY` in your shell. Without
it, the normalizer falls back to a "delegate" mode that emits a JSON
payload your conversational LLM (Claude Code / Copilot) can use to do
the rewrite itself via its Edit/Write tool — so the workflow keeps
working even with no API key.

### Invoking the normalizer

The same command works on every OS thanks to the self-bootstrap:

    python scripts/normalize_jira_story.py jira-stories/PROJ-124.txt --diagram PROJ-123-20260524-045255.drawio

If your shell's `python` resolves to the Microsoft Store stub or
nothing at all, use `python3` on Linux/macOS or `py` on Windows — any
Python 3 interpreter works as the launcher because the script
immediately re-execs under the venv Python it finds for your OS.

The per-OS wrappers below are equivalent and remain available:

| OS | Wrapper (optional) |
|---|---|
| macOS | `./scripts/mac/normalize.sh jira-stories/PROJ-124.txt --diagram PROJ-123-20260524-045255.drawio` |
| Linux | `./scripts/linux/normalize.sh jira-stories/PROJ-124.txt --diagram PROJ-123-20260524-045255.drawio` |
| Windows | `.\scripts\windows\normalize.ps1 jira-stories\PROJ-124.txt --diagram PROJ-123-20260524-045255.drawio` |

Useful flags (forwarded by the wrappers):

| Flag | Purpose |
|---|---|
| `--diagram <name>` | Switch to UPDATE mode: embed the target diagram's `read_diagram_summary` so the rewrite quotes existing labels verbatim. Omit for CREATE mode. |
| `--check` | Report whether `<KEY>-surgical.txt` exists and is canonical. Exit 0 if OK, 2 if not. |
| `--dry-run` | Print the rewrite to stdout without writing any file. |
| `--force` | Re-run the LLM rewrite even if the surgical file is already canonical (useful when the target diagram has drifted). |
| `--output <path>` | Override the auto-derived `<KEY>-surgical.txt` destination. |
| `--model <id>` | Anthropic model id (default `claude-sonnet-4-6`; override via env var `NORMALIZER_MODEL`). |
| `--template <path>` | Reference template that the rewrite must match structurally (default `jira-stories/DEMO-001.txt`). |
| `--diagrams-dir <path>` | Diagrams root (default `<repo>/diagrams`). |

### Exit codes

| Code | Meaning |
|---|---|
| 0 | `REFRESHED (copy)` — input was already canonical, mirrored to surgical without an LLM call (CREATE mode only); or `REFRESHED (LLM)` — LLM rewrite written successfully; or `FORMAT_OK` — only when `--skip-if-fresh` was passed and the existing surgical was kept. **Always-fresh is the default** — every invocation regenerates the surgical from the current source unless `--skip-if-fresh` is given. |
| 1 | Hard error (story file missing, args malformed, template missing). |
| 2 | `NEEDS_NORMALIZATION` — either `--check` reported a non-canonical surgical, or the LLM rewrite couldn't run (no SDK, no API key) and the JSON delegate payload was emitted on stdout. |

---

## Diagram verifier

`scripts/verify_mcp.py` is a cross-platform pre-finalization gate. The
`create-diagram` and `update-diagram` prompts run it after the last
mutating MCP call and before printing the final summary. It detects
two classes of failure that have actually bitten this repo:

- **Server import / registry breakage** — if a recent refactor left a
  tool unregistered or the package broken, `tools/list` would be
  missing entries. The verifier imports the registry directly and
  confirms all 13 expected tools are present.
- **Half-done structural edits** — dangling edges left by a partial
  `remove_element`, duplicate labels from a forgotten relabel, or GCP
  services drawn as plain rectangles (i.e. the `gcp_icon` step was
  skipped). These are mechanical checks that don't require parsing
  the story.

### Invocation

The same command on every OS (self-bootstraps under the venv):

    python scripts/verify_mcp.py                            # server only
    python scripts/verify_mcp.py --diagram PROJ-XXX.drawio  # server + diagram
    python scripts/verify_mcp.py --diagram PROJ-XXX.drawio --strict

If your shell's `python` resolves to nothing, use `python3` (Linux/macOS)
or `py` (Windows) — any Python 3.10+ will work as the launcher.

### Flags

| Flag | Purpose |
|---|---|
| `--diagram <name>` | Also run structural checks on this diagram (under `--diagrams-dir`). Omit for server-only. |
| `--diagrams-dir <path>` | Diagrams root (default `<repo>/diagrams`). |
| `--icons-dir <path>` | GCP icons root (default `<repo>/logo_icon_gcp`). |
| `--strict` | Treat warnings (duplicate labels, missing GCP icons) as failures. By default they're shown but don't fail the run. |

### Exit codes

| Code | Meaning |
|---|---|
| 0 | All checks passed. |
| 2 | Verification failure — missing tool, dangling edge, or (in `--strict`) duplicate labels / missing GCP icons. Error details printed to stderr. |

Note: the per-OS `verify.sh` / `verify.ps1` scripts under `mac/`,
`linux/`, `windows/` are unchanged. They probe the running MCP server
via stdio JSON-RPC and are mostly useful right after a fresh
`setup.sh` to confirm the install survived. `scripts/verify_mcp.py`
is the in-flow pre-finalization gate driven by the diagram prompts.

---

## Quickstart

### macOS

```bash
cd /path/to/architecture_building_ai_solution
chmod +x scripts/mac/*.sh
./scripts/mac/setup.sh                    # full install: brew, python, git, MCP server, VS Code config
./scripts/mac/verify.sh
./scripts/mac/demo.sh                     # optional — drops the sample story
```

For a fully unattended install (incl. Copilot extensions):
```bash
./scripts/mac/setup.sh --with-extensions --yes
```

See [mac/README.md](mac/README.md) for the full list of flags.

### Linux

```bash
cd /path/to/architecture_building_ai_solution
bash scripts/linux/setup.sh
bash scripts/linux/verify.sh
bash scripts/linux/demo.sh        # optional — drops the sample story
```

You can also `chmod +x scripts/linux/*.sh` once and then run them as
`./scripts/linux/setup.sh`. The Linux scripts assume you've already
installed Python 3.10+ and Git via your distro's package manager.

### Windows (PowerShell)

```powershell
cd C:\path\to\architecture_building_ai_solution
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
powershell -ExecutionPolicy Bypass -File scripts\windows\verify.ps1
powershell -ExecutionPolicy Bypass -File scripts\windows\demo.ps1
```

Or, if you've already allowed local scripts:
```powershell
.\scripts\windows\setup.ps1
```

---

## After setup

Whichever path you took, finish in VS Code:

1. ⇧⌘P / Ctrl+Shift+P → **Developer: Reload Window**.
2. Open Copilot Chat → click the MCP/tools indicator → confirm
   **drawio** is connected with 13 tools.
3. In Copilot Chat:
   ```
   @workspace Use the prompt at prompts/create-diagram.md.
   The story is jira-stories/DEMO-001.txt.
   Save the diagram as diagrams/demo-001.drawio.
   ```

See [docs/execution.md](../docs/execution.md) for the full daily-use
walkthrough.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `python3: command not found` (Linux) | Install Python 3.10+ first. `setup.sh` prints the right command for your distro. |
| `python3: command not found` (macOS) | Run `./scripts/mac/setup.sh` without `--skip-prereqs` — it will install `python@3.12` via Homebrew automatically. |
| `python: command not found` (Windows) | Install via `winget install Python.Python.3.12` then re-open PowerShell. |
| `cannot be loaded because running scripts is disabled` (Windows) | Use `powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1`. |
| `verify.sh` says "fewer than 13 tools" | Re-run `setup.sh` — the editable install probably failed. Look for `pip install -e .` errors above. |
| Scripts run but VS Code still shows the server as failed | The script updated `mcp.json` correctly; reload the VS Code window. |
