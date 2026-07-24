# Execution guide

How to actually **use** the system once installation (see
[installation.md](installation.md)) is complete. Follow the numbered
phases top-to-bottom — each phase ends with a clear "you should now see…"
checkpoint so you can confirm progress before moving on.

> Throughout this guide:
> - The **workspace root** is the folder `AI_Atlassian_copilot/`.
> - The **server folder** is `AI_Atlassian_copilot/drawio-mcp-server/`.
> - All commands assume macOS / Linux shells. On Windows PowerShell,
>   replace `source .venv/bin/activate` with `.\.venv\Scripts\Activate.ps1`.

---

## Phase 0 — Pre-flight checks

Before running anything, confirm the install is healthy.

```bash
# 1. You're inside the project root
cd "/path/to/AI_Atlassian_copilot"

# 2. The venv exists
ls drawio-mcp-server/.venv/bin/python   # macOS / Linux
# dir drawio-mcp-server\.venv\Scripts\python.exe   # Windows

# 3. The package is installed in that venv
drawio-mcp-server/.venv/bin/python -m pip show drawio-mcp-server
```

Expected: the `pip show` command prints `Name: drawio-mcp-server` with a
version. If it errors, redo
[installation.md Step 8](installation.md#step-8--install-the-mcp-server-in-editable-mode).

---

## Phase 1 — Start VS Code with the MCP server attached

1. Open the workspace folder in VS Code:
   ```bash
   code "/path/to/AI_Atlassian_copilot"
   ```
2. Reload the window once:
   **⇧⌘P** (mac) / **Ctrl+Shift+P** (win/linux) → `Developer: Reload Window`.
3. Open Copilot Chat (chat icon in the activity bar, or **⌃⌘I** /
   **Ctrl+Alt+I**).
4. In the chat input area, click the **MCP servers** indicator (looks
   like a small plug/stack icon).

**Checkpoint:**
You should see one server listed: **`drawio` — connected**, with 10
tools underneath: `list_diagrams`, `read_diagram`, `read_diagram_summary`,
`create_diagram`, `add_node`, `add_edge`, `update_node`,
`remove_element`, `list_stories`, `read_story`.

If you see "failed" instead, open **View → Output → MCP** and re-do
[installation.md Step 10](installation.md#step-10--point-vs-code-at-the-venvs-python-if-needed).

---

## Phase 2 — Drop the Jira story

The system never talks to Jira directly. You feed it a downloaded story
as a plain text/markdown file.

### 2a. Get the story content
- In Jira, open the story.
- Either **Export → Word/PDF**, or simply select the description and
  copy it into a new file.

### 2b. Save it under `jira-stories/`
File name should be the Jira key for traceability:
```bash
# Example: paste your story body into this file
echo "<paste story content here>" > jira-stories/PROJ-123.txt
```

For a first run with no real story yet, copy the bundled example:
```bash
cp examples/sample-jira-story.txt jira-stories/PROJ-123.txt
```

**Checkpoint:**
```bash
ls jira-stories/
# → .gitkeep   PROJ-123.txt
```

---

## Phase 3 — Decide: create a new diagram, or update an existing one?

Use this quick decision rule:

| Situation | Use |
|---|---|
| No `.drawio` covers this part of the system yet | **Create flow** (Phase 4) |
| There's an existing diagram and the story changes its components | **Update flow** (Phase 5) |
| Unsure | Run the **Update flow** with the closest existing diagram — Copilot will tell you if it can't fit and suggest creating a new one |

To see what diagrams already exist:
```bash
ls diagrams/
```

---

## Phase 4 — Create a new diagram (run this in Copilot Chat)

### 4a. Send the prompt
Paste **exactly this** into Copilot Chat (replace the two `{{...}}` placeholders):

```text
@workspace Use the prompt at prompts/create-diagram.md.
The story is jira-stories/{{PROJ-123.txt}}.
Save the diagram as diagrams/{{order-notification.drawio}}.
```

Real example:
```text
@workspace Use the prompt at prompts/create-diagram.md.
The story is jira-stories/PROJ-123.txt.
Save the diagram as diagrams/order-notification.drawio.
```

### 4b. What Copilot will do (in order)
1. Call `read_story` → loads the requirement text.
2. Identify components (services, DBs, queues, actors, externals).
3. Call `create_diagram` → makes an empty `.drawio` file.
4. Call `add_node` repeatedly → one per component, with the right shape.
5. Call `add_edge` repeatedly → one per relationship.
6. Print a short summary of what it added and the absolute file path.

### 4c. Approve / steer
If Copilot asks for confirmation before each tool call (depends on your
VS Code setting **`chat.tools.autoApprove`**), click **Continue** to
approve. To stop and adjust, just say "stop, change X to Y" — Copilot
will revise.

**Checkpoint:**
```bash
ls diagrams/
# → ... order-notification.drawio
```

Skip to Phase 6 to verify visually.

---

## Phase 5 — Update an existing diagram (run this in Copilot Chat)

### 5a. Send the prompt
```text
@workspace Use the prompt at prompts/update-diagram.md.
The story is jira-stories/{{PROJ-123.txt}}.
The diagram is diagrams/{{system.drawio}}.
```

Real example:
```text
@workspace Use the prompt at prompts/update-diagram.md.
The story is jira-stories/PROJ-123.txt.
The diagram is diagrams/system.drawio.
```

### 5b. What Copilot will do (in order)
1. Call `read_story` → loads the requirement.
2. Call `read_diagram_summary` → cheap label-only view of the current diagram.
3. **Wait for your approval of the change plan** — this is a hard rule
   in the prompt template, so you get to review before any file is touched.
4. Once you say "approved" / "go ahead", Copilot applies edits one tool
   call at a time:
   - `add_node` for new components,
   - `add_edge` for new relationships,
   - `update_node` to rename or change shape (preserves position),
   - `remove_element` for retired components or stale edges.
5. Print a bullet list of changes and the saved file path.

### 5c. If you want to abort
Type "cancel" or "don't apply that" before approving — no file is
written until step 4 above.

**Checkpoint:**
```bash
git diff diagrams/system.drawio
```
You should see only the lines for components/edges that the story
actually changed — manual layout (node positions you set in draw.io)
must be preserved.

---

## Phase 6 — Verify the result visually

### 6a. Open the .drawio file in VS Code
With the **Draw.io Integration** extension installed
([installation.md Step 5](installation.md#step-5--install-the-drawio-vs-code-extension)),
double-click the file in the Explorer. It opens in the draw.io editor.

### 6b. Sanity checks
- Every component mentioned in the story is present.
- Every relationship in the story is drawn (with the right direction
  and a meaningful label).
- Shape conventions match (cylinder = DB, queue = broker, actor =
  user, cloud = external SaaS — see
  [tool-reference.md](tool-reference.md#shape-vocabulary-add_node--update_node)).

### 6c. Tweak by hand if needed
You can drag, resize, or recolor freely in the draw.io editor.
**Save with "Compressed" unchecked** (Extras → Edit Diagram → uncheck
Compressed → Apply → Ctrl+S) so the next MCP read still works.

---

## Phase 7 — Commit the change

The whole point of saving uncompressed XML is reviewable diffs.

```bash
git status
git diff diagrams/                              # XML diff is human-readable
git add diagrams/order-notification.drawio
git commit -m "Add architecture diagram for PROJ-123 order email flow"
```

If your team commits Jira stories alongside diagrams:
```bash
git add jira-stories/PROJ-123.txt
```
Otherwise leave them out (or add `jira-stories/*` to `.gitignore`).

---

## Phase 8 — Iterate

Common follow-ups:

| Goal | Command in Copilot Chat |
|---|---|
| Add one more component to the same diagram | `Add a Redis cache between the Notification Service and SendGrid in diagrams/order-notification.drawio.` |
| Rename a component | `Rename "Notification Service" to "Email Notification Service" in diagrams/order-notification.drawio.` |
| Remove a component | `Remove the Audit DB from diagrams/order-notification.drawio.` |
| Start over | Delete the file from `diagrams/` and re-run Phase 4. |

You don't always need a Jira story — once a diagram exists, you can ask
Copilot to amend it conversationally and it will use the same MCP tools.

---

## Phase 9 — Stop / restart the server

You normally don't stop the server manually — VS Code starts it when
Copilot Chat opens and stops it when the window closes. To force a
restart (for example after editing the server's Python source):

1. ⇧⌘P / Ctrl+Shift+P → **MCP: Restart Server** → pick `drawio`.
2. Or just reload the window: ⇧⌘P / Ctrl+Shift+P → `Developer: Reload Window`.

---

## End-to-end execution checklist

Use this every time, top-to-bottom:

- [ ] Phase 0 — venv exists, package installed
- [ ] Phase 1 — VS Code shows `drawio` MCP server **connected** with 10 tools
- [ ] Phase 2 — Jira story saved as `jira-stories/<KEY>.txt`
- [ ] Phase 3 — Decided create vs update
- [ ] Phase 4 or 5 — Ran the matching prompt; reviewed Copilot's plan
- [ ] Phase 6 — Opened the `.drawio` file and visually verified
- [ ] Phase 7 — Committed the diff
- [ ] Phase 8 — Iterated if needed

If any phase fails, jump to its **Checkpoint** block — that line tells
you exactly what success looks like, so you know which step regressed.
