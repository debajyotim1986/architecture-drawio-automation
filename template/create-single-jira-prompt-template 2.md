# Create-Diagram Prompt Template — SINGLE Jira story

Use this when you have **one** Jira story and no existing diagram covers it.

**How to use:** copy everything in the fenced block below into Copilot Chat
(or Claude), then replace `{{STORY_FILE}}` with your story's filename
(e.g. `PROJ-126.txt`). The `drawio` MCP server must be running.

The full reference (with the stylish-output checklist and per-step rationale)
lives in [`prompts/create-diagram.md`](../prompts/create-diagram.md). This file
is the trimmed, ready-to-paste version.

---

```text
I have a Jira story summary at `jira-stories/{{STORY_FILE}}` describing a new
capability. Please:

0. Normalize the story first. Run, in a terminal before any MCP call:

       python scripts/normalize_jira_story.py jira-stories/{{STORY_FILE}}

   This regenerates `jira-stories/<KEY>-surgical.txt` on every invocation
   (the original is never modified; the prior surgical is backed up to
   `<KEY>-surgical.txt.bak`). The script self-bootstraps under the project
   venv, so the same command works on macOS / Linux / Windows (use `python3`
   or `py` if `python` isn't on PATH).
   - Exit 0 (REFRESHED copy / REFRESHED LLM / FORMAT_OK) → proceed to step 1.
   - Exit 2 with a `NEEDS_NORMALIZATION` JSON payload → no Anthropic key/SDK
     was available. Use your Write tool to CREATE the file at the payload's
     `target_path` as a build-from-scratch canonical story (shape of
     `template/surgical-story-template.txt`; `jira-stories/PROJ-123.txt`
     is a filled-in worked example), then re-run with `--check` until FORMAT_OK.
   - Any other exit code → STOP and report the error.

1. Call `read_story` with `name="<KEY>-surgical.txt"` (NOT the original
   `{{STORY_FILE}}`). Derive `<KEY>` from the filename: `PROJ-126.txt` →
   `PROJ-126-surgical.txt`.

2. Identify the components implied by the story: services, databases, queues,
   external systems, and the actors that interact with them.

3. Call `create_diagram` with `jira_key="<KEY>"` (e.g. `jira_key="PROJ-126"`)
   and a descriptive `title`. Do NOT pass `name` — the server builds a
   timestamped filename `<KEY>-YYYYMMDD-HHMMSS.drawio` so re-runs never
   overwrite. Use the resolved `name` from the response in every subsequent
   call.

4. (Optional) Title banner via `add_title` — only if I explicitly ask for one.
   Skip by default; the swimlanes already convey the structure.

5. LAYER THE DIAGRAM — call `add_container` BEFORE any `add_node`. Group the
   components into 4-6 logical layers and create one swimlane per layer, in
   left-to-right reading order, with a `color_hint` from the palette:
   `external` (red) → `ingestion` (blue) → `processing` (yellow) →
   `staging` (green) → `curation` (purple) → `serving` (orange) →
   `observability` (gray) → `security` (deeper red). Do NOT pass
   `column_index`/`x`. Capture each returned `id` to use as `parent_id`.
   Skip layers that would have no nodes.

6. Add each component with `add_node(..., parent_id=<container id>)` so it
   nests in the right swimlane. Do NOT pass `x`/`y` for nested nodes.
   - GCP RULE (MANDATORY): for every Google Cloud service, pass
     `gcp_icon="<service>"` (case/space/underscore-insensitive — "BigQuery",
     "cloud_sql", "pubsub", "GKE", "Vertex AI"). A GCP service drawn as a
     plain stencil is a bug.
   - Use `shape="actor"` for users, `shape="cloud"` for non-GCP SaaS,
     `shape="queue"` for non-GCP brokers (Kafka/RabbitMQ).

7. Self-check: scan your `add_node` calls; for any GCP-service label created
   without `gcp_icon` (and not reported as `auto_detected_gcp_icon`), fix it
   with `update_node(..., gcp_icon="<service>")`.

8. Connect components with `add_edge`. Labels describe the relationship
   (`publishes`, `reads`, `HTTPS`) — keep them <= 3 words / ~24 chars. The
   server auto-numbers edges ("1. uploads", "2. object event", ...), fans out
   parallel edges, routes cross-container edges through empty gaps, and frames
   busy nodes. Call edges in the order the data flows. Pass `step=N` to force
   ordering or `step=0` to suppress a back-edge's number.

9. Verify before finalizing. Run:

       python scripts/verify_mcp.py --diagram <SAVED_DIAGRAM_FILE>

   (use the resolved `name` from step 3). It checks the tool registry, no
   dangling edges, no duplicate labels, every GCP node uses its icon, every
   edge renders an arrowhead, and parallel edges are fanned out.
   Exit 0 → step 10. Exit 2 → STOP, fix with `update_node`/`remove_element`,
   re-verify.

10. Generate the connector-details table. Run:

       python scripts/generate_connector_details.py \
           --diagram <SAVED_DIAGRAM_FILE> \
           --story  jira-stories/<KEY>-surgical.txt

    With `ANTHROPIC_API_KEY` set, the script writes a fully filled
    `jira-stories/<KEY>-connectors.md` (exit 0). Without it, exit 2 emits a
    `NEEDS_FILL` payload — you must edit the .md, replacing every `{TBD}` per
    the Always-Fill rule (surgical story → GCP defaults → engineering
    inference). `{TBD}` in any form is BANNED — use `(assumed)`/`(default)`
    for business-decision fields. The next step's guard refuses to embed if
    any `{TBD}` remains.

11. Embed the table: call `add_connector_table(diagram="<SAVED_DIAGRAM_FILE>")`.
    It reads `<KEY>-connectors.md` and lays a styled table below the swimlanes,
    one row per numbered edge. Idempotent.

12. Finish with a short bullet summary (which nodes used `gcp_icon`, the
    step-numbered flow, the connector-details file path, that the table is
    embedded) and the saved diagram path.

Do not read or write anything outside `diagrams/` and `jira-stories/`. Make
one MCP call at a time and keep edits minimal — I'll review the diff.
```
