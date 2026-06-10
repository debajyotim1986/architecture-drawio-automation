# Prompt — Update an existing architecture diagram from a Jira story

Use this when there is already a diagram that covers the affected area.

---

I have a Jira story at `jira-stories/{{STORY_FILE}}` that changes part of
our architecture. The current diagram is `diagrams/{{DIAGRAM_FILE}}`.
Please:

0. **Normalize the story first — diagram-aware (surgical) mode.** Run

       python scripts/normalize_jira_story.py jira-stories/{{STORY_FILE}} --diagram {{DIAGRAM_FILE}}

   in a terminal before any MCP call. **The normalizer regenerates
   `<KEY>-surgical.txt` on every invocation by default** — no flag
   is needed to force this. In UPDATE mode the rewrite always goes
   through the LLM (or the delegate fallback) so the new surgical
   quotes the CURRENT labels from `{{DIAGRAM_FILE}}` verbatim, no
   matter how stale a previous `<KEY>-surgical.txt` was. The previous
   surgical (if any) is backed up to `<KEY>-surgical.txt.bak`.

   This single command works on macOS, Linux, and Windows: the
   script self-bootstraps — on first import it detects the host OS
   via `sys.platform`, locates the project venv Python
   (`.venv/bin/python` on macOS/Linux, `.venv\\Scripts\\python.exe`
   on Windows), and re-execs itself under that interpreter so the
   `anthropic` and `drawio_mcp_server` imports always resolve. If
   your shell's `python` isn't on PATH, use `python3` (Linux/macOS)
   or `py` (Windows). Per-OS wrapper scripts also exist as a
   fallback — `scripts/mac/normalize.sh`,
   `scripts/linux/normalize.sh`, `scripts/windows/normalize.ps1` —
   but you don't need them; the bootstrap handles OS detection. The normalizer NEVER modifies
   the input file. It writes a sibling file
   `jira-stories/<KEY>-surgical.txt` (e.g. `PROJ-124.txt` →
   `PROJ-124-surgical.txt`) that downstream steps consume. Because
   `--diagram` is supplied, the rewrite embeds the current diagram's
   `read_diagram_summary` into the LLM prompt so the surgical file
   quotes existing node and edge labels verbatim — this is what gives
   section 3 its explicit REMOVE / ADD lists and section 7 its
   Before → After ASCII flow.
   - Exit code `0` with `REFRESHED (LLM)` → expected outcome in
     UPDATE mode. The LLM regenerated `<KEY>-surgical.txt` against
     the current source AND the current diagram. Proceed to step 1.
   - Exit code `0` with `REFRESHED (copy)` → uncommon in UPDATE mode
     (would mean the source was already canonical AND no diagram
     context to weave in — but `--diagram` was passed, so this path
     should not normally fire). Proceed to step 1.
   - Exit code `0` with `FORMAT_OK` → only happens if someone passed
     `--skip-if-fresh`. The existing surgical was kept as-is. Proceed
     to step 1 only if you are confident it still matches the
     current diagram; otherwise re-run without `--skip-if-fresh`.
   - Exit code `2` with a `NEEDS_NORMALIZATION` JSON payload → the
     Anthropic SDK / API key wasn't available. The payload contains
     `source_story_path`, `target_path`, `current_diagram_summary`,
     `reference_template`, and `raw_story_text`. Use your Write tool
     to CREATE the file at `target_path` (NOT to overwrite
     `source_story_path`) as a SURGICAL-DIFF story (shape of
     [`jira-stories/PROJ-124.txt`](../jira-stories/PROJ-124.txt)):
     section 3 must list nodes/edges to REMOVE and ADD using labels
     quoted verbatim from `current_diagram_summary`; section 7 must
     contain ASCII Before → After flows; section 10 acceptance
     criteria must be verifiable against `read_diagram_summary`;
     every existing edge whose endpoint is being removed must be
     rerouted or deleted (no dangling edges). Re-run the normalizer
     with `--check` to confirm `FORMAT_OK` before proceeding.
   - Any other exit code → STOP and report the error.
1. Call `read_story` with `name="<KEY>-surgical.txt"` (NOT the
   original `{{STORY_FILE}}`). Derive `<KEY>` from the input
   filename — `PROJ-124.txt` → `PROJ-124-surgical.txt`. The surgical
   file is the canonical, prompt-consumable requirement; the original
   raw note is left untouched as a human-readable source of truth.
2. Call `read_diagram_summary` on the current diagram. Do **not** read the
   full diagram unless the summary is insufficient — this saves tokens and
   keeps you focused on topology rather than coordinates.
3. Compare the two and produce a short plan listing exactly what should be
   added, renamed, removed, or reconnected. **Wait for me to approve the
   plan** before making changes.
4. After I approve, apply the plan one tool call at a time:
   - `add_node` for new components,
   - `add_edge` for new connections,
   - `update_node` to rename, change shape, or swap in a GCP icon
     (preserves position),
   - `remove_element` for retired components or stale edges.
   - **GCP rule:** any newly added node that represents a Google Cloud
     service must use the official GCP icon. Pass the service name in
     `gcp_icon` on `add_node` (e.g. `gcp_icon="BigQuery"`) — the server
     resolves the SVG and sets size to 64×64 automatically. You do not
     need to read, encode, or paste any SVG yourself.
     If an existing generic node clearly represents a GCP service (e.g.
     a plain rectangle labelled "BigQuery"), include an `update_node`
     call in the plan with `gcp_icon=...` to swap it — flag it in the
     plan so I can approve the visual change.
5. **Verify before finalizing.** After the last mutating MCP call,
   run

       python scripts/verify_mcp.py --diagram <SAVED_DIAGRAM_FILE>

   where `<SAVED_DIAGRAM_FILE>` is the name returned by the create /
   save call (the timestamped output, not the source). This is a
   pre-finalization gate: it confirms the MCP server's tool registry
   is healthy AND that the diagram is structurally sound (no dangling
   edges whose endpoints were deleted, no duplicate node labels left
   over from a half-done split, and every GCP-named node uses its
   official icon). Exit 0 → finalize. Exit 2 → STOP, surface the
   reported errors / warnings to me, and fix them with the appropriate
   MCP tool calls (typically `remove_element` for stale edges or
   `update_node` with `gcp_icon=…` for missing icons) before
   re-running verify. The script self-bootstraps under the project
   venv, so the same command works on macOS / Linux / Windows.
6. End with a bullet list of the actual changes and the saved file path.

Do not rewrite the diagram from scratch. Preserve existing node ids and
positions wherever possible — the user has manually laid this out.

---

## Multiple stories

This template covers the **single-story** update flow. For multiple
stories landing in one sprint:

1. **Explicit sequence** — list the story files in the prompt; they are
   processed in the order you list them. See
   [`prompt.md` → Prompt 2: Batch-update](prompt.md#prompt-2--batchupdate-multiple-stories--existing-diagram-in-place)
   for the canonical template.

2. **Default order (low-to-high)** — to apply *every* story currently in
   `jira-stories/`, ask Copilot to call `list_stories` first and process
   the result in the order returned. `list_stories` is natural-sorted, so
   keys come back numerically ascending: `PROJ-2` before `PROJ-10` before
   `PROJ-100`.

Drop-in prompt for the default-order case:

```text
@workspace Apply EVERY story currently under jira-stories/ to
diagrams/{{DIAGRAM_FILE}} in natural-ascending key order.

1. Call list_stories to get the canonical low-to-high order. Filter
   out names ending in `-surgical.txt` — those are generated outputs,
   not raw inputs.
2. For EACH raw story file in that order, run
   `python scripts/normalize_jira_story.py jira-stories/<file> --diagram {{DIAGRAM_FILE}}`
   in a terminal. **Always-fresh is the default** — every
   invocation regenerates the surgical against the current source
   AND the current diagram. The normalizer writes a sibling
   `<file-stem>-surgical.txt` next to each input; the original is
   untouched. Exit `0` (REFRESHED / FORMAT_OK) → proceed. Exit `2`
   with `NEEDS_NORMALIZATION` → `Write` the new file at the
   payload's `target_path` using `current_diagram_summary` +
   `reference_template`, then re-run until exit 0.
3. Call read_story on each SURGICAL file in the original order (e.g.
   `read_story(name="<KEY>-surgical.txt")`).
4. Call read_diagram_summary on the diagram.
5. Produce ONE consolidated change plan grouped by story key, then
   STOP and wait for my approval.
6. After approval, apply changes one tool call at a time using
   add_node / add_edge / update_node / remove_element.
7. **Verify before finalizing.** Run
   `python scripts/verify_mcp.py --diagram {{DIAGRAM_FILE}}`. Exit 0
   → done. Exit 2 → STOP, fix the reported errors / warnings with
   `update_node` / `remove_element`, re-verify.
8. End with a bullet list grouped by story key, then the saved file path.

If two stories conflict, STOP and ask me which to honor — do not pick
silently.
```
