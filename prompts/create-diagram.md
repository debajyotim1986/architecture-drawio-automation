# Prompt — Create a new architecture diagram from a Jira story

Use this when no existing diagram covers the area described in the story.

> ## 📋 How to use this prompt
>
> **For a SINGLE Jira story (the common case):**
> Copy **lines 59–323** of this file into Copilot Chat — that's
> everything between the `▼▼▼ COPY FROM HERE ▼▼▼` marker on line 56
> and the `▲▲▲ STOP COPYING HERE ▲▲▲` marker on line 326. Then
> replace `{{STORY_FILE}}` with your story's filename (e.g.
> `PROJ-126.txt`). Do NOT include this checklist block above, the
> markers themselves, or the "Multiple stories" section at the
> bottom — just the body between the two markers.
>
> The marker comments are HTML comments (`<!-- ... -->`), so even if
> you accidentally include them in the paste, they're invisible to
> the LLM and harmless.
>
> **For MULTIPLE Jira stories landing in one sprint:**
> See the [Multiple stories](#multiple-stories) section at the bottom
> instead. That section has its own copy-pasteable drop-in template.

> **Stylish-output checklist** — every diagram produced by this
> prompt must satisfy ALL of the following before it's considered
> finished. The numbered steps below are sequenced so that doing
> each one delivers the corresponding item:
> 1. **Layered swimlanes**, one per architectural concern (External /
>    Ingestion / Processing / Staging / Curation / Observability /
>    Security as relevant), each with a distinct header color. Built
>    in step 5 via `add_container`.
> 2. **GCP icons for every GCP service** (BigQuery, Pub/Sub, Cloud
>    Composer, Dataproc, Cloud Storage, ...). Plain rectangles for
>    GCP services are a bug. Built in step 6 via `add_node(...,
>    gcp_icon=...)`, audited in steps 7 (self-check) and 9 (verifier).
> 3. **Cross-container connectors with visible arrows** — every edge
>    must render its arrowhead solidly. Style is set automatically by
>    the server; step 9's verifier hard-fails if an edge would render
>    arrowless.
> 4. **Numbered connectors in flow order** — every edge label is
>    prefixed with its 1-based step number (`"1. uploads"`,
>    `"2. object event"`, ...) so a reader can follow the data flow
>    sequentially. Auto-assigned by `add_edge`.
> 5. **Per-connector documentation table** — `<KEY>-connectors.md`
>    with one row per numbered edge, covering interaction pattern,
>    protocol, auth, data, network, performance, reliability,
>    observability, compliance, and dependencies. Generated in step 10
>    via `scripts/generate_connector_details.py`.
> 6. **Table embedded below the diagram** — a styled in-canvas
>    rendering of the same connector details (Step | Source | Target |
>    Action | Details) positioned below the swimlanes, so opening the
>    .drawio file shows BOTH the architecture and the per-connector
>    contract on the same canvas. Built in step 11 via the
>    `add_connector_table` MCP tool, sourced from the same
>    `<KEY>-connectors.md`.
>
> If you finish all 12 steps and the verifier in step 9 returned
> exit 0, all six checklist items are satisfied.

---

<!-- ===================================================================== -->
<!-- ▼▼▼ COPY FROM HERE ▼▼▼  (start of the single-story prompt body)     -->
<!-- ===================================================================== -->

I have a Jira story summary at `jira-stories/{{STORY_FILE}}` describing a new
capability. Please:

0. **Normalize the story first.** Run

       python scripts/normalize_jira_story.py jira-stories/{{STORY_FILE}}

   in a terminal before any MCP call. **The normalizer regenerates
   `<KEY>-surgical.txt` on every invocation by default** — no flag
   is needed to force this. In CREATE mode, if the source is already
   structurally canonical the regen is just a verbatim copy (no LLM
   call). If the source is raw / partial / has stale boilerplate
   (the realistic case), the LLM rewrite path runs. Either way, the
   surgical file on disk after step 0 reflects the CURRENT contents
   of `{{STORY_FILE}}`. The previous surgical (if any) is backed up
   to `<KEY>-surgical.txt.bak`.

   This single command works on macOS, Linux, and Windows: the
   script self-bootstraps — it detects the host OS via
   `sys.platform`, locates the project venv Python
   (`.venv/bin/python` on macOS/Linux, `.venv\\Scripts\\python.exe`
   on Windows), and re-execs itself under it. If your shell's
   `python` isn't on PATH, use `python3` (Linux/macOS) or `py`
   (Windows). Per-OS wrapper scripts also exist as a fallback
   (`scripts/{mac,linux}/normalize.sh`,
   `scripts/windows/normalize.ps1`) but you don't need them.

   The normalizer NEVER modifies the input file. It writes a sibling
   file `jira-stories/<KEY>-surgical.txt` (e.g. `PROJ-125.txt` →
   `PROJ-125-surgical.txt`) that downstream steps consume. A
   `<KEY>-surgical.txt.bak` of the previous surgical version (if any)
   is written before overwrite so you can see what changed run-to-run.
   - Exit code `0` with `REFRESHED (copy)` → expected when the source
     was already structurally canonical (rare in real business
     usage). Surgical mirrors the source verbatim. Proceed to step 1.
   - Exit code `0` with `REFRESHED (LLM)` → expected when the source
     is raw or has stale boilerplate. The LLM produced a clean
     surgical. Proceed to step 1.
   - Exit code `0` with `FORMAT_OK` → only happens if someone passed
     `--skip-if-fresh`. Proceed to step 1, but be aware the existing
     surgical was kept as-is (no refresh).
   - Exit code `2` with a `NEEDS_NORMALIZATION` JSON payload → the
     Anthropic SDK / API key wasn't available. The payload contains
     `source_story_path`, `target_path`, `reference_template`, and
     `raw_story_text`. Use your Write tool to CREATE the file at
     `target_path` (NOT to overwrite `source_story_path`) as a
     build-from-scratch canonical story matching the shape of the
     payload's `reference_template`
     ([`template/surgical-story-template.txt`](../template/surgical-story-template.txt);
     [`jira-stories/PROJ-123.txt`](../jira-stories/PROJ-123.txt) is a
     filled-in worked example). Re-run the normalizer with `--check` to
     confirm `FORMAT_OK` before proceeding.
   - Any other exit code → STOP and report the error.
1. Call `read_story` with `name="<KEY>-surgical.txt"` (NOT the
   original `{{STORY_FILE}}`). Derive `<KEY>` from the input
   filename — `PROJ-125.txt` → `PROJ-125-surgical.txt`. The surgical
   file is the canonical requirement; the original is left untouched.
2. Identify the components implied by the story: services, databases,
   queues, external systems, and the actors that interact with them.
2a. **Restricted-service guardrail (MANDATORY — before you write anything).**
   Read [`policy/unavailable_services.md`](../policy/unavailable_services.md)
   and check every component you identified in step 2 — its label AND the
   `gcp_icon` you plan to use — against the restricted list (matching is
   case/space/underscore-insensitive and covers each entry's aliases).
   - If nothing matches, proceed to step 3 silently.
   - If one or more components match a restricted service: do NOT create
     the diagram or any node yet. For each match, offer alternatives drawn
     **only** from the `alternate1`–`alternate4` candidates in the
     **Service alternatives reference** table in that same file (the
     restricted list itself has no alternatives), **ranked by how well each
     fits this Jira story's scenario** (best fit first, with a one-line
     reason).
     **Drop any candidate that is itself restricted** (alias-aware) and
     take the next allowed one; if all four are restricted, keep going down
     the chain until only non-restricted services remain. Never offer a
     restricted service as an alternative. Then **ask the user, in one
     prompt, which replacement to use** (one
     numbered option group per restricted service). **STOP and wait** for
     their choice. Once they pick, substitute the approved service
     (label + `gcp_icon`) into your plan, then continue. Never place a
     restricted service and never pick the alternative for them.
3. Call `create_diagram` with **`jira_key`** set to the story's Jira key
   (e.g. `jira_key="PROJ-123"` — derive it from the story filename you
   passed to `read_story`) and a descriptive `title`. **Do not pass
   `name`**: the server will build the filename as
   `<JIRA_KEY>-YYYYMMDD-HHMMSS.drawio` so re-running this prompt always
   produces a fresh diagram without overwriting prior ones. The tool's
   response includes the resolved `name` — use that exact value for every
   subsequent `add_title` / `add_container` / `add_node` / `add_edge` call.
4. **Optional — title banner.** A `add_title` MCP tool exists for
   adding a styled bold banner above the swimlanes (good for
   deck-quality diagrams shared outside the team). Call it only when
   the user explicitly asks for a title or you have strong context
   that one is needed. Skip it by default — the swimlane structure
   itself already communicates the architecture clearly, and the
   diagram filename + Jira key carry the identifying info.

5. **LAYER THE DIAGRAM — call `add_container` BEFORE any `add_node`.** A flat 4-column grid of nodes is the OLD default and
   reads as "basic"; a labeled swimlane per architectural layer is
   what makes the diagram look professional. From the components you
   identified in step 2, group them into 4–6 logical layers and call
   `add_container` once per layer, in left-to-right reading order:
   - Typical layer set for a GCP data pipeline:
     `External / On-Prem` → `Ingestion` → `Processing` → `Staging` →
     `Curation` → `Observability` (and optionally `Security` /
     `Serving`). Pick whichever subset fits the story.
   - Pick a `color_hint` per layer from the curated palette so the
     reader can follow data flow at a glance: `external` (red) for
     on-prem / non-GCP sources, `ingestion` (blue), `processing`
     (yellow), `staging` (green), `curation` (purple), `serving`
     (orange), `observability` (gray), `security` (deeper red).
   - Do NOT pass `column_index` or `x` unless you have a specific
     non-LR layout in mind — the server places each new container in
     the next column slot automatically (**240 px wide, 140 px gap**,
     left-to-right). The wide gap leaves enough room between layers
     for the orthogonal edge router AND for the busy-node card
     border (added automatically when a node has >3 connectors) to
     stand clear of its neighbour.
   - The response includes `id` — capture it and use it as
     `parent_id` on every `add_node` call that belongs to this layer.
   - Skip layers that wouldn't have any nodes (e.g. no Security
     services in scope → don't create a Security swimlane).
6. Add each component using `add_node`, **passing `parent_id=<the
   container id from step 5>`** so the node nests inside the right
   swimlane. Inside a container the server auto-stacks children
   vertically with proper spacing for 64×64 GCP icons + labels — do
   NOT pass `x` / `y` for nested nodes.
   - Top-level nodes (not in any swimlane) are still allowed but
     should be rare — only use them for things genuinely outside the
     layered model (e.g. a global legend, or an actor that interacts
     with multiple layers).
   - Follow the shape conventions in
     `.github/copilot-instructions.md` (cylinder for db, queue for broker,
     actor for users, cloud for external SaaS).
   - **GCP rule (MANDATORY).** For every node that represents a Google
     Cloud service, pass `gcp_icon="<service>"` on `add_node`. Do NOT
     use a stencil shape (`rounded`, `cylinder`, `rectangle`, …) for a
     GCP service — that produces a colourless, generic-looking diagram.
     The server inlines the official SVG and sizes the node to 64×64.
     Required, not optional, for any service from this list (and the
     ones aliased to it):
     - Compute / serverless: Cloud Run, Cloud Functions, App Engine,
       Compute Engine, GKE / Kubernetes Engine, Anthos, Cloud TPU
     - Databases: BigQuery, Cloud SQL, Cloud Spanner, Bigtable,
       Firestore, Datastore, Memorystore, AlloyDB
     - Storage: Cloud Storage / GCS, Filestore, Persistent Disk
     - Messaging / data: Pub/Sub, Dataflow, Dataproc, Cloud Composer,
       Eventarc, Workflows, Cloud Tasks, Cloud Scheduler, Datastream,
       Data Fusion
     - AI / ML: Vertex AI, Dialogflow, Document AI, AutoML
     - Networking / security: Apigee, Cloud Load Balancing, Cloud CDN,
       Cloud Armor, Cloud NAT, Cloud DNS, Cloud VPN, VPC, IAM,
       Identity Platform, Secret Manager, KMS, API Gateway
     - Observability: Cloud Logging, Cloud Monitoring, Cloud Trace,
       Error Reporting
     - DevOps: Cloud Build, Cloud Deploy, Artifact Registry,
       Container Registry
     `gcp_icon` is case/space/underscore-insensitive — `"BigQuery"`,
     `"bigquery"`, `"big query"`, `"BIGQUERY"` all work.
     Example: `add_node(diagram=..., label="Orders DB (Cloud SQL)",
     gcp_icon="Cloud SQL")`.
     **Safety net:** if you forget `gcp_icon` but the label names a GCP
     service, the server auto-detects it and returns
     `auto_detected_gcp_icon` in the response — but rely on explicit
     `gcp_icon` so you can see the choice in the tool call.
   - For users / actors use `shape="actor"`. For external non-GCP SaaS
     (e.g. SendGrid, Stripe, Slack) use `shape="cloud"`. For Kafka /
     RabbitMQ / other non-GCP brokers use `shape="queue"`.
   - **Layout is automatic when `parent_id` is set.** The server
     stacks children vertically inside their swimlane (16-px left
     padding, 50-px top offset below the header, **200-px vertical
     stride** — leaves ~136 px clear between adjacent icons so the
     orthogonal edge router has horizontal "lanes" to use without
     crossing icons OR squashing connector labels against icon-name
     labels). Swimlanes themselves are separated by **140-px gaps**
     so cross-column edges bend in a wide empty corridor and any
     busy-node card border (auto-applied when a node has >3
     connectors) has clearance from the next column. Do NOT pass
     `x` / `y` for nested nodes — let the container layout handle
     it. For a top-level node (no `parent_id`), the server falls
     back to the 4-column wrap grid just like before.

7. **Self-check before finishing.** Mentally scan your `add_node`
   calls. For every node whose label mentions any service in the list
   above and was NOT created with `gcp_icon` (and was not reported as
   `auto_detected_gcp_icon` in the response), fix it now with
   `update_node(diagram=..., id=..., gcp_icon="<service>")`. A diagram
   that contains Cloud Run / BigQuery / Pub/Sub etc. as plain
   rectangles is a bug — do not deliver it.
8. Connect components with `add_edge`. Edge labels should describe the
   relationship (`publishes`, `reads`, `HTTPS`, …). Cross-container
   edges (a node in one swimlane → a node in another) are exactly
   how the pipeline flow shows up visually, so don't be shy with them.
   - **Auto-parallel routing.** When 2+ edges share a source OR a
     target, the server automatically spreads their exit/entry
     fractions across the node's perimeter (`exitY`, `entryY` in
     [0.2, 0.8]) so the orthogonal router fans them out in parallel
     instead of stacking them on the same line. You don't have to
     pass any layout hint — just call `add_edge` as usual. The
     step-9 verifier hard-fails on stacked-edge regressions, so any
     case the auto-spread misses gets caught before finalization.
   - **Auto-numbered step labels.** Each `add_edge` call automatically
     gets a 1-based sequence number rendered as a `"N. <label>"`
     prefix on the edge label above the line (e.g. `"1. uploads"`,
     `"7. loads raw"`). Drawio renders this in the same white pill
     that holds the edge text, so the number is always visible above
     the connector across every renderer (desktop / web / VS Code
     extension) without any per-renderer rendering risk. You don't
     have to manage the numbers — just call `add_edge` in the order
     the data should flow and the labels come out 1, 2, 3, …. To
     override (e.g. for a parallel branch that should share a step
     number), pass `step=N` explicitly. To suppress the number
     entirely (e.g. for a "back" edge that shouldn't be in the
     count), pass `step=0`. The number is reachable later as the
     structured `step_index` field on each edge — see
     `jira-stories/<KEY>-connectors.md` produced in step 10 for the
     full per-connector detail table indexed by step number.
   - **Label length rule.** Keep edge labels to **≤ 3 words / ~24
     characters**. Labels sit on a white pill above the line, but a
     long label still stretches horizontally and collides with adjacent
     node labels. Prefer `"publishes"` over
     `"publishes OrderPlaced event"`, `"reads templates"` over
     `"reads email templates from PostgreSQL"`. Put the verbose
     description in the Jira story, not on the wire.
   - **Text-vs-connector rule.** You do **not** need to set any style
     yourself — the server already guarantees connector labels render
     in a distinct Google-blue bold above the line. The serializer
     emits two mechanisms per labeled edge:
     (1) the edge style includes `align=center;verticalAlign=bottom;`
     plus `fontColor=#0B57D0;fontStyle=1;fontSize=11;` (label colour
     and weight that distinguish connector text from black icon-name
     labels) and `labelBackgroundColor=#ffffff;` (the white pill that
     keeps the label readable when it crosses another edge), and
     (2) a `<mxPoint x="0" y="-22" as="offset" />` geometry point
     that physically lifts the label 22 px above the line in every
     renderer. If you open a generated diagram and labels are sitting
     **on** the arrow, the MCP server is running stale Python from
     before this fix — stop and ask the user to follow
     `Installation Guide/vscode-restart-formality.md` (the
     short version is `pkill -f drawio_mcp_server` + Reload Window).
     Do not try to work around the symptom with custom styles.
   - **Busy-node card.** Nothing to do — when a node ends up with more
     than 3 incoming + outgoing connectors, the server automatically
     wraps the icon in a thin rounded-rectangle "card" border. This
     signals "this is a hub" visually AND gives the surrounding
     connector labels a non-icon edge to butt up against (so they
     never get mistaken for the icon's own name label). The behaviour
     lives in `_frame_busy_nodes` in `tools/add_edge.py`; you don't
     trigger it explicitly.
   - **Skip-edge note (top-level layout only).** When every node is
     nested in a swimlane, the orthogonal edge router routes through
     the gaps between containers automatically — you don't need to
     worry about edge labels colliding with node labels. The old
     "avoid long skip edges" caveat only applies if you've placed
     nodes at the top level (no `parent_id`) on the 4-column wrap
     grid; in that case, an edge from column 0 to column 3 can pass
     over intermediate nodes. Prefer swimlanes for everything except
     legends / one-off floating nodes.
9. **Verify before finalizing.** After the last mutating MCP call,
   run

       python scripts/verify_mcp.py --diagram <SAVED_DIAGRAM_FILE>

   where `<SAVED_DIAGRAM_FILE>` is the timestamped name returned by
   `create_diagram` (use the resolved `name` from its response, not
   `{{STORY_FILE}}`). This is a pre-finalization gate that confirms:
   - The MCP server's tool registry is healthy.
   - The diagram has **no dangling edges** (every edge endpoint
     resolves to an existing node — catches a partial `remove_element`).
   - **No duplicate node labels** (catches half-done splits).
   - **Every GCP-named node uses its official icon** (catches a
     missed `gcp_icon=` — what step-7 self-check should have caught).
   - **Every edge will render its arrowhead** — the validator parses
     each edge's `style` string and errors if `endArrow=` is missing,
     `endArrow=none`, or `endFill=` is missing/zero (the
     "arrowhead-as-hairline-outline" failure mode that produces
     connectors without visible arrows in certain renderers).
   - **Parallel edges fanned out** — when 2+ edges share a source or
     target, each must have a distinct `entryY` / `exitY` fraction
     so the orthogonal router doesn't stack them on the same line.
     Warnings (fatal under `--strict`) fire on stacked endpoints.

   Exit 0 → proceed to step 10. Exit 2 → STOP, surface the errors /
   warnings, and fix them with `update_node` / `remove_element`
   before re-running verify. The script self-bootstraps under the
   project venv, so the same command works on macOS / Linux / Windows.
10. **Generate the connector-details table (AUTO-FILLED).** After
    verify is green, run

        python scripts/generate_connector_details.py \
            --diagram <SAVED_DIAGRAM_FILE> \
            --story  jira-stories/<KEY>-surgical.txt

    in a terminal. **Default `--fill auto` behavior:**
    - If `ANTHROPIC_API_KEY` is set, the script calls Claude (model
      `claude-sonnet-4-6` by default) with the surgical story +
      schema reference + skeleton table and **writes back a FULLY
      FILLED `jira-stories/<KEY>-connectors.md`** — every detail
      cell carries a real value from the Always-Fill priority list
      (surgical story → GCP defaults → engineering inference). You
      do NOT have to edit the file manually in this case; the
      script does the work for you. Exit code `0`, proceed.
    - If `ANTHROPIC_API_KEY` is unset OR the SDK is unavailable, the
      script exits `2` with a `NEEDS_FILL` JSON payload on stdout
      containing the schema, the surgical story, and the skeleton.
      The payload's `instructions_for_calling_llm` field tells you
      (the conversational LLM running this prompt) to **edit
      `<KEY>-connectors.md` via your Write tool, replacing every
      `{TBD}` per the Always-Fill rule, BEFORE moving to step 11.**
      Skipping this is not an option — step 11's
      `add_connector_table` has a hard pre-flight guard that
      refuses to embed if more than 5 unqualified `{TBD}` cells
      remain.

    **Always-Fill priority list** (used by both auto-fill and
    delegate paths):
    1. **Surgical story** — section 3 names components and
       connections, sections 5–6 carry FRs/NFRs.
    2. **GCP architectural defaults** — e.g. `Cloud Storage` edge →
       HTTPS / REST / 443 / Service Account / TLS 1.3 /
       Google-managed CMEK; `Pub/Sub` → Async / Event-Driven /
       at-least-once / JSON or Avro / IAM-scoped subscribers;
       `Cloud Composer → Dataproc` → gRPC over IAM-auth SA channel.
    3. **Engineering inference** — idempotent + jittered retry,
       structured logs to Cloud Logging, RED metrics to Cloud
       Monitoring, P95 in hundreds-of-ms.

    Each cell must follow the **sub-field shape** defined in
    [docs/connector-details-template.md](../docs/connector-details-template.md).

    **`{TBD}` in any form is BANNED in the deliverable** — even for
    fields that genuinely require business-stakeholder input.
    Replace them with **sensible defaults labelled `(assumed)` or
    `(default)`** so the cell renders as a concrete value the
    reviewer can confirm or override:
    - `Reg scope: SOC 2 + GDPR (assumed for EU-origin data)` ← good
    - `Throughput: 100 RPS avg (default; confirm with capacity)` ← good
    - `Reg scope: {TBD: GDPR if EU-origin data}` ← REJECTED

    The step-11 `add_connector_table` MCP tool has a zero-tolerance
    pre-flight guard that fails if ANY `{TBD}` token (plain OR
    qualified `{TBD: <hint>}`) remains in the file.

    The script self-bootstraps under the project venv so the same
    command works on macOS, Linux, and Windows. If the file already
    exists from a prior run, the previous version is preserved as
    `<KEY>-connectors.md.bak`.

11. **Embed the connector-details table BELOW the diagram.** Call
    `add_connector_table(diagram="<SAVED_DIAGRAM_FILE>")`. This
    builds a styled table directly inside the .drawio canvas
    positioned below the swimlanes, with one row per numbered edge.
    Columns: `Step | Source | Target | Action | Details`. The
    `Details` cell concatenates all 10 connector-detail categories
    (Interaction, Protocol & API, AuthN/Z, Data, Network, Performance,
    Reliability, Observability, Compliance, Dependencies) into one
    HTML cell with `<br>`-separated lines per field.

    The tool reads `jira-stories/<KEY>-connectors.md` automatically
    (the file the step-10 generator just produced) and threads each
    row's field values into the matching diagram cell. Fields still
    marked `{TBD}` in the .md show as `{TBD}` in the diagram cell —
    so reviewing the diagram visually surfaces exactly which fields
    still need attention. Idempotent: if the table is already in the
    diagram from a previous call, the old cells are removed before
    the new layout is laid down. The single source of truth stays
    `<KEY>-connectors.md`; the diagram-embedded table is a
    derived view.

12. Finish with a short bullet summary of what you created (calling out
    which nodes used `gcp_icon`, the step-numbered flow sequence, the
    connector-details file path, and that the table is embedded in
    the diagram below the swimlanes) and the saved diagram file path.

Do **not** read or write anything outside `diagrams/` and `jira-stories/`.
Make one MCP call at a time and keep edits minimal — I'll review the diff.

<!-- ===================================================================== -->
<!-- ▲▲▲ STOP COPYING HERE ▲▲▲  (end of the single-story prompt body)    -->
<!-- ===================================================================== -->

---

## Multiple stories

This template covers the **single-story** create flow. For multi-story
flows there are two ways to drive it:

1. **Explicit sequence** — list the story files in the prompt; they are
   processed in the order you list them. See
   [`prompt.md` → Prompt 1: Fork-and-merge](prompt.md#prompt-1--forkandmerge-multiple-stories--new-diagram-copy)
   for the canonical template.

2. **Default order (low-to-high)** — if you want Copilot to pick up
   *every* story in `jira-stories/`, ask it to call `list_stories` first
   and process the result in the order returned. `list_stories` is
   natural-sorted, so Jira keys come back in numeric order
   (`PROJ-2` before `PROJ-10` before `PROJ-100`).

Drop-in prompt for the default-order case:

```text
@workspace Use the prompt at prompts/create-diagram.md, but apply it to
EVERY Jira story in jira-stories/ (not just one).

1. Call list_stories to get the canonical low-to-high order. Filter
   out names ending in `-surgical.txt` — those are generated outputs,
   not raw inputs.
2. For EACH raw story file in that order, run
   `python scripts/normalize_jira_story.py jira-stories/<file>` in
   a terminal. **Always-fresh is the default** — every invocation
   regenerates the surgical from the current source. The normalizer
   writes a sibling `<file-stem>-surgical.txt` next to each input;
   the original is untouched. Exit `0` (REFRESHED / FORMAT_OK) →
   proceed. Exit `2` with `NEEDS_NORMALIZATION` → `Write` the new
   file at the payload's `target_path` using the payload's
   `reference_template`, then re-run until exit 0.
3. Call read_story on each SURGICAL file in the original order (e.g.
   `read_story(name="<KEY>-surgical.txt")`).
4. Synthesise the components/relationships across all stories before
   creating the diagram.
5. Call create_diagram with jira_key set to the LOWEST Jira key in the
   batch (e.g. jira_key="PROJ-2"). The server timestamps the filename so
   re-runs don't overwrite. Use the resolved `name` from the response
   for all subsequent add_node / add_edge calls.
6. Then add_node / add_edge per the merged plan.
7. **Verify before finalizing.** Run
   `python scripts/verify_mcp.py --diagram <SAVED_DIAGRAM_FILE>` where
   `<SAVED_DIAGRAM_FILE>` is the timestamped name from step 5's
   response. Exit 0 → done. Exit 2 → fix the reported errors and
   re-verify.

If two stories conflict (e.g. one adds a component another removes),
STOP and ask me which to honor before continuing.
```

