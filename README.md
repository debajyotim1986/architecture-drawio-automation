# Architecture Building — AI Solution

A local Python **Model Context Protocol** server that turns business
requirements (Jira stories, Confluence pages, plain text) into
deck-quality **draw.io architecture diagrams** through a single
GitHub Copilot Chat prompt.

> Same MCP server works with any MCP-aware LLM client — GitHub Copilot,
> Claude Desktop, Cursor, or your own client. The reference setup is
> VS Code + Copilot Chat.

---

## What you get out of the box

| Component | Where | What it does |
|---|---|---|
| `drawio-mcp-server/` | Python MCP server | Exposes 13 intent-level tools (`add_container`, `add_node`, `add_edge`, …) over stdio JSON-RPC |
| `scripts/` | Cross-platform helpers | Install, verify, normalize Jira stories, generate connector-detail tables, retrofit existing diagrams |
| `prompts/` | Copy-paste prompts | The 12-step `create-diagram.md` flow + the incremental `update-diagram.md` flow |
| `logo_icon_gcp/` | 258 official GCP SVGs | Pluggable icon catalog — drop more SVG folders in to support AWS / Azure / on-prem |
| `policy/unavailable_services.md` | Governance guardrail | Editable list of disallowed services — checked before any diagram is written; the assistant proposes an approved alternative and asks you to pick |
| `.vscode/mcp.json` | VS Code wiring | Tells Copilot how to launch the local server |
| `.github/copilot-instructions.md` | Repo-wide rules | Auto-attached to every Copilot Chat turn |

---

## Quickstart (5 minutes)

### macOS / Linux

```bash
# 1. Install (creates the venv, installs the package, patches .vscode/mcp.json)
./scripts/linux/setup.sh

# 2. Probe the server — should print "All 13 expected tools are present."
./scripts/linux/verify.sh

# 3. Reload VS Code (⇧⌘P → Developer: Reload Window).
#    Open Copilot Chat and confirm "drawio" is connected with 13 tools.
```

### Windows

```powershell
# 1. Install
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1

# 2. Probe
powershell -ExecutionPolicy Bypass -File scripts\windows\verify.ps1

# 3. Reload VS Code, then check the MCP servers panel.
```

Full step-by-step is in [`docs/installation.md`](docs/installation.md).

---

## Day-to-day usage

The fastest path is the **plain-English shorthand** — drop your story in
`jira-stories/` and just tell Copilot Chat what you want, no long prompt
to paste:

```
Jira: PROJ-123.txt, based on the jira pls create a diagram
Jira: PROJ-123.txt, based on the jira pls update a diagram
Jira: PROJ-123.txt, PROJ-124.txt, based on the jira pls create a diagram
```

Copilot recognizes the shorthand (rule lives in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md)),
figures out **create vs. update**, **which story file(s)**, and (for an
update) **which diagram** to patch, then runs the full backend flow
(`prompts/create-diagram.md` or `prompts/update-diagram.md`) end-to-end.
For an update with no diagram named, it auto-picks the one matching the
Jira key, or asks if there's more than one.

Under the hood that expands to the same pipeline you can also drive
manually:

```
1. Drop a business requirement into  jira-stories/<KEY>.txt
2. Normalize it:                     ./scripts/linux/normalize.sh <KEY>
3. Open Copilot Chat, paste:         prompts/create-diagram.md
4. Copilot drives the 13 MCP tools → diagrams/<KEY>-<timestamp>.drawio
5. Verify:                           ./scripts/linux/verify.sh
6. Open the .drawio in the draw.io VS Code extension.
```

Full workflow with examples is in [`docs/usage.md`](docs/usage.md).

---

## Folder layout

```
architecture_building_ai_solution/
├── README.md                       (this file)
├── .github/copilot-instructions.md (repo-wide rules — auto-attached to Copilot)
├── .vscode/mcp.json                (Copilot ↔ MCP server wiring)
├── Installation Guide/             (mandatory restart procedure)
├── drawio-mcp-server/              (the Python MCP server — full code + tests)
│   ├── pyproject.toml
│   ├── src/drawio_mcp_server/      (server, tools, drawio adapter, util)
│   └── tests/
├── logo_icon_gcp/                  (258 official GCP SVG icons)
├── policy/
│   └── unavailable_services.md     (disallowed services — checked before every diagram)
├── scripts/                        (cross-platform helpers + per-OS wrappers)
│   ├── normalize_jira_story.py     (raw prose → 10-section surgical doc)
│   ├── verify_mcp.py               (pre-finalization health check)
│   ├── generate_connector_details.py (14-column connector-detail table)
│   ├── reroute_diagram.py          (retrofit an existing .drawio with new layout)
│   ├── linux/  *.sh                (Linux / macOS wrappers)
│   └── windows/  *.ps1             (Windows PowerShell wrappers)
├── prompts/
│   ├── create-diagram.md           (PRIMARY — 12-step create flow)
│   └── update-diagram.md           (incremental update flow)
├── docs/
│   ├── installation.md             (full install instructions)
│   ├── usage.md                    (daily workflow)
│   └── tool-reference.md           (13 MCP tools + shape vocabulary)
├── jira-stories/                   (input — put your requirements here)
└── diagrams/                       (output — generated .drawio files land here)
```

---

## The 13 MCP tools (at a glance)

**Read-only.** `list_diagrams`, `read_diagram`, `read_diagram_summary`,
`list_stories`, `read_story`.

**Mutating.** `create_diagram`, `add_container` (swimlanes),
`add_node` (icons), `add_edge` (routed connectors), `add_title`,
`add_connector_table` (14-col detail table), `update_node`,
`remove_element`.

Detailed schema in [`docs/tool-reference.md`](docs/tool-reference.md).

---

## Critical: VS Code restart formality

VS Code's *MCP: Restart Server* command does **not** reliably kill the
child Python process. Stale Python in RAM is the #1 cause of
"my code change didn't take effect". Before every diagram session
run the restart checklist in
[`Installation Guide/vscode-restart-formality.md`](Installation%20Guide/vscode-restart-formality.md).

---

## Roadmap (next two weeks → go-live)

- [ ] Validate the install scripts on a clean Windows VM.
- [ ] Run the smoke test (`scripts/linux/demo.sh`) on Linux.
- [ ] Onboard the first team — collect their feedback on prompt clarity.
- [ ] Tag a `v1.0` release.

---

## Support

- Engineering owner: **Debajyoti Mukhopadhyay**
- For framework questions: open an issue or reach out internally.
