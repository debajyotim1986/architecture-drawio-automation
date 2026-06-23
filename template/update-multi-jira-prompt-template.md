# Update-Diagram Prompt Template — MULTIPLE Jira stories

Use this when **several** Jira stories should be applied to **one existing
diagram**, in place (e.g. a sprint's worth of changes). It patches the diagram
— it does NOT rebuild from scratch, so manual layout is preserved. There are
two ways to drive it:

- **Explicit sequence** — list the specific story files; they are applied in
  the order you list them.
- **Default order (low-to-high)** — let Copilot pick up *every* story in
  `jira-stories/` via `list_stories`, natural-sorted so keys come back
  numerically (`PROJ-2` before `PROJ-10` before `PROJ-100`).

The full reference lives in
[`prompts/update-diagram.md` → Multiple stories](../prompts/update-diagram.md#multiple-stories).
This file is the trimmed, ready-to-paste version. Replace `{{DIAGRAM_FILE}}`
with the target diagram filename. The `drawio` MCP server must be running.

---

## Option A — every story in `jira-stories/`, natural-ascending order

```text
@workspace Apply EVERY story currently under jira-stories/ to
diagrams/{{DIAGRAM_FILE}} in natural-ascending key order, in place.

1. Call list_stories to get the canonical low-to-high order. Filter out names
   ending in `-surgical.txt` and `-connectors.md` — those are generated
   outputs, not raw inputs.
2. For EACH raw story file in that order, run in a terminal:
       python scripts/normalize_jira_story.py jira-stories/<file> --diagram {{DIAGRAM_FILE}}
   Always-fresh is the default — every run regenerates `<stem>-surgical.txt`
   against the current source AND current diagram (original untouched). Exit 0
   (REFRESHED/FORMAT_OK) → proceed. Exit 2 with NEEDS_NORMALIZATION → Write the
   surgical-diff file at the payload's `target_path` using
   `current_diagram_summary` + `reference_template`, then re-run until exit 0.
3. Call read_story on each SURGICAL file in the original order
   (read_story(name="<KEY>-surgical.txt")).
4. Call read_diagram_summary on {{DIAGRAM_FILE}}.
5. Produce ONE consolidated change plan grouped by story key, then STOP and
   wait for my approval.
6. After approval, apply changes one tool call at a time using add_node /
   add_edge / update_node / remove_element. GCP services MUST use gcp_icon;
   edge labels <= 3 words. No dangling edges — reroute or delete any edge whose
   endpoint a story removes.
7. Verify before finalizing:
       python scripts/verify_mcp.py --diagram {{DIAGRAM_FILE}}
   Exit 0 → done. Exit 2 → STOP, fix with update_node / remove_element,
   re-verify.
8. End with a bullet list grouped by story key, then the saved file path.

If two stories conflict (one adds what another removes), STOP and ask me which
to honor — do not pick silently. Preserve existing node ids and positions
wherever possible. Do not read or write anything outside `diagrams/` and
`jira-stories/`.
```

---

## Option B — an explicit list of stories, in the order I give

Replace the `STORIES` list with your filenames.

```text
@workspace Apply these Jira stories, IN THIS ORDER, to diagrams/{{DIAGRAM_FILE}}
in place:

STORIES:
  1. {{STORY_FILE_1}}    (e.g. PROJ-124.txt)
  2. {{STORY_FILE_2}}    (e.g. PROJ-128.txt)
  3. {{STORY_FILE_3}}    (e.g. PROJ-131.txt)

1. For EACH story above, in the listed order, run:
       python scripts/normalize_jira_story.py jira-stories/<file> --diagram {{DIAGRAM_FILE}}
   Exit 0 → proceed. Exit 2 with NEEDS_NORMALIZATION → Write the surgical-diff
   file at the payload's `target_path` (quoting current_diagram_summary labels
   verbatim), then re-run until exit 0.
2. Call read_story(name="<KEY>-surgical.txt") for each, in the listed order.
3. Call read_diagram_summary on {{DIAGRAM_FILE}}.
4. Produce ONE consolidated change plan grouped by story key, then STOP and
   wait for my approval.
5. After approval, apply changes one tool call at a time using add_node /
   add_edge / update_node / remove_element. GCP services MUST use gcp_icon;
   keep edge labels <= 3 words; no dangling edges.
6. Run: python scripts/verify_mcp.py --diagram {{DIAGRAM_FILE}}
   Exit 0 → done. Exit 2 → fix and re-verify.
7. End with a bullet list grouped by story key and the saved file path.

If two stories conflict, STOP and ask me which to honor — do not pick silently.
Preserve existing node ids and positions wherever possible. Do not read or
write anything outside `diagrams/` and `jira-stories/`.
```
