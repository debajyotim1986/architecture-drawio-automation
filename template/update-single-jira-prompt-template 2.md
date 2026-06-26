# Update-Diagram Prompt Template — SINGLE Jira story

Use this when a diagram **already exists** for the affected area and one Jira
story changes part of it. This patches the diagram in place — it does NOT
rebuild from scratch, so your manual layout is preserved.

**How to use:** copy the fenced block into Copilot Chat (or Claude), then
replace `{{STORY_FILE}}` with the story filename (e.g. `PROJ-124.txt`) and
`{{DIAGRAM_FILE}}` with the existing diagram filename (e.g.
`PROJ-123-20260524-045255.drawio`). The `drawio` MCP server must be running.

The full reference lives in [`prompts/update-diagram.md`](../prompts/update-diagram.md).
This file is the trimmed, ready-to-paste version.

---

```text
I have a Jira story at `jira-stories/{{STORY_FILE}}` that changes part of our
architecture. The current diagram is `diagrams/{{DIAGRAM_FILE}}`. Please:

0. Normalize the story first — diagram-aware (surgical) mode. Run, in a
   terminal before any MCP call:

       python scripts/normalize_jira_story.py jira-stories/{{STORY_FILE}} --diagram {{DIAGRAM_FILE}}

   Because `--diagram` is supplied, the rewrite always goes through the LLM (or
   delegate fallback) so the new `<KEY>-surgical.txt` quotes the CURRENT labels
   from {{DIAGRAM_FILE}} verbatim — that is what gives section 3 its explicit
   REMOVE / ADD lists and section 7 its Before → After ASCII flow. The original
   is never modified; the prior surgical is backed up to `<KEY>-surgical.txt.bak`.
   The script self-bootstraps under the project venv (same command on
   macOS / Linux / Windows; use `python3` or `py` if needed).
   - Exit 0 with REFRESHED (LLM) → expected. Proceed to step 1.
   - Exit 2 with a `NEEDS_NORMALIZATION` JSON payload → no Anthropic key/SDK.
     Use your Write tool to CREATE the file at the payload's `target_path` as a
     SURGICAL-DIFF story (shape of `jira-stories/PROJ-124.txt`): section 3 lists
     nodes/edges to REMOVE and ADD using labels quoted verbatim from
     `current_diagram_summary`; section 7 has ASCII Before → After flows;
     section 10 acceptance criteria are verifiable against read_diagram_summary;
     every edge whose endpoint is removed must be rerouted or deleted (no
     dangling edges). Re-run with `--check` until FORMAT_OK.
   - Any other exit code → STOP and report the error.

1. Call `read_story` with `name="<KEY>-surgical.txt"` (NOT the original
   {{STORY_FILE}}). Derive `<KEY>` from the filename: `PROJ-124.txt` →
   `PROJ-124-surgical.txt`.

2. Call `read_diagram_summary` on {{DIAGRAM_FILE}}. Do NOT read the full diagram
   unless the summary is insufficient — it saves tokens and keeps you on
   topology, not coordinates.

3. Compare the two and produce a short plan listing exactly what to add,
   rename, remove, or reconnect. WAIT for me to approve the plan before
   making any changes.

4. After I approve, apply the plan one tool call at a time:
   - `add_node` for new components (GCP services MUST pass gcp_icon="<service>"),
   - `add_edge` for new connections (labels <= 3 words; auto-numbered/routed),
   - `update_node` to rename / change shape / swap in a GCP icon (preserves
     position),
   - `remove_element` for retired components or stale edges.
   If an existing generic node clearly represents a GCP service (e.g. a plain
   rectangle labelled "BigQuery"), include an `update_node(..., gcp_icon=...)`
   in the plan and flag the visual change for my approval.

5. Verify before finalizing:

       python scripts/verify_mcp.py --diagram <SAVED_DIAGRAM_FILE>

   It confirms the tool registry is healthy, no dangling edges (catches a
   partial remove_element), no duplicate labels (catches a half-done split),
   and every GCP-named node uses its icon. Exit 0 → finalize. Exit 2 → STOP,
   surface the errors, fix with update_node / remove_element, re-verify.

6. End with a bullet list of the actual changes and the saved file path.

Do not rewrite the diagram from scratch. Preserve existing node ids and
positions wherever possible — I have manually laid this out. Do not read or
write anything outside `diagrams/` and `jira-stories/`.
```
