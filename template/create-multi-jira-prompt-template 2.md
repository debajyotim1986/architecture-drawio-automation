# Create-Diagram Prompt Template — MULTIPLE Jira stories

Use this when several Jira stories should be **merged into one new diagram**
(e.g. all stories landing in a sprint). There are two ways to drive it:

- **Explicit sequence** — list the specific story files in the prompt; they
  are processed in the order you list them.
- **Default order (low-to-high)** — let Copilot pick up *every* story in
  `jira-stories/` via `list_stories`, which is natural-sorted so Jira keys
  come back numerically (`PROJ-2` before `PROJ-10` before `PROJ-100`).

The full reference lives in
[`prompts/create-diagram.md` → Multiple stories](../prompts/create-diagram.md#multiple-stories).
This file is the trimmed, ready-to-paste version. The `drawio` MCP server must
be running.

---

## Option A — every story in `jira-stories/`, natural-ascending order

Copy the block below into Copilot Chat as-is (no placeholders to fill).

```text
@workspace Use the create-diagram flow, but apply it to EVERY Jira story in
jira-stories/ (not just one), merged into ONE new diagram.

1. Call list_stories to get the canonical low-to-high order. Filter out names
   ending in `-surgical.txt` and `-connectors.md` — those are generated
   outputs, not raw inputs.
2. For EACH raw story file in that order, run in a terminal:
       python scripts/normalize_jira_story.py jira-stories/<file>
   Always-fresh is the default — every run regenerates `<stem>-surgical.txt`
   from the current source (original untouched). Exit 0 (REFRESHED/FORMAT_OK)
   → proceed. Exit 2 with NEEDS_NORMALIZATION → Write the new file at the
   payload's `target_path` using its `reference_template`, then re-run until
   exit 0.
3. Call read_story on each SURGICAL file in the original order
   (read_story(name="<KEY>-surgical.txt")).
4. Synthesise the components and relationships ACROSS all stories before
   creating the diagram. De-duplicate shared components (one Cloud Storage,
   one BigQuery, etc.) and reconcile overlapping flows.
5. Call create_diagram with jira_key set to the LOWEST Jira key in the batch
   (e.g. jira_key="PROJ-2"). The server timestamps the filename. Use the
   resolved `name` from the response for all subsequent calls.
6. LAYER FIRST: add_container 4-6 times (one per architectural layer, with a
   color_hint), THEN add_node(..., parent_id=<id>, gcp_icon=...) per merged
   component (GCP services MUST use gcp_icon), THEN add_edge per connection
   (labels <= 3 words; edges auto-number, fan out, and route automatically).
7. Verify before finalizing:
       python scripts/verify_mcp.py --diagram <SAVED_DIAGRAM_FILE>
   Exit 0 → step 8. Exit 2 → fix with update_node/remove_element, re-verify.
8. Generate + embed the connector table:
       python scripts/generate_connector_details.py \
           --diagram <SAVED_DIAGRAM_FILE> --story jira-stories/<KEY>-surgical.txt
   (fill every {TBD} per the Always-Fill rule — no {TBD} in the deliverable),
   then call add_connector_table(diagram="<SAVED_DIAGRAM_FILE>").
9. Finish with a bullet summary grouped by story key and the saved diagram
   path.

If two stories conflict (one adds a component another removes), STOP and ask
me which to honor before continuing.
```

---

## Option B — an explicit list of stories, in the order I give

Copy the block below, then replace the `STORIES` list with your filenames.

```text
@workspace Use the create-diagram flow to merge these Jira stories, IN THIS
ORDER, into ONE new diagram:

STORIES:
  1. {{STORY_FILE_1}}    (e.g. PROJ-201.txt)
  2. {{STORY_FILE_2}}    (e.g. PROJ-202.txt)
  3. {{STORY_FILE_3}}    (e.g. PROJ-203.txt)

1. For EACH story above, in the listed order, run:
       python scripts/normalize_jira_story.py jira-stories/<file>
   Exit 0 → proceed. Exit 2 with NEEDS_NORMALIZATION → Write the canonical
   file at the payload's `target_path`, then re-run until exit 0.
2. Call read_story(name="<KEY>-surgical.txt") for each, in the listed order.
3. Synthesise a single merged set of components and connections, de-duplicating
   anything shared across stories.
4. Call create_diagram with jira_key set to the FIRST listed story's key. Use
   the resolved `name` for every subsequent call.
5. LAYER FIRST (add_container per layer with a color_hint), then
   add_node(..., parent_id=<id>, gcp_icon=...) per component (GCP services MUST
   use gcp_icon), then add_edge per connection (labels <= 3 words).
6. Run: python scripts/verify_mcp.py --diagram <SAVED_DIAGRAM_FILE>
   Exit 0 → step 7. Exit 2 → fix and re-verify.
7. Generate the connector table with generate_connector_details.py (fill every
   {TBD}), then embed it with add_connector_table(diagram="<SAVED_DIAGRAM_FILE>").
8. Finish with a bullet summary grouped by story key and the saved diagram path.

If two stories conflict, STOP and ask me which to honor — do not pick silently.
Do not read or write anything outside `diagrams/` and `jira-stories/`.
```
