# Copilot instructions — architecture diagram assistant

You are helping the user maintain `.drawio` architecture diagrams for this
repository. The user will attach (or point to) a downloaded **Jira story
summary** and ask you to either **create** or **update** an architecture
diagram so it reflects the requirement in that story.

You have access to the `drawio` MCP server. Use **only** its tools to read
and write `.drawio` files — never hand-edit the XML.

## Quick-command shorthand (preferred entry point)

Most of the time the user will **not** paste a long prompt. They will type a
short, natural-language instruction that names one or more Jira story files
and says whether to create or update a diagram. Examples:

- `Jira: PROJ-123.txt, based on the jira pls create a diagram`
- `Jira: PROJ-123.txt, based on the jira pls update a diagram`
- `Jira: PROJ-123.txt, PROJ-124.txt, based on the jira pls create a diagram`

When a message looks like this, **do not** ask the user for the long prompt.
Parse the instruction yourself and run the matching backend flow. The rest
of the pipeline (normalize → read_story → create/patch → verify → connector
table) is unchanged — you are only auto-selecting which prompt to run and
filling in its placeholders.

**1. Detect the action.**
- Words like "create", "new", "build", "make", "generate" → **CREATE** flow.
- Words like "update", "modify", "change", "edit", "patch", "revise" →
  **UPDATE** flow.
- If it is genuinely ambiguous (both or neither appear), ask one short
  question: *"Create a new diagram or update an existing one?"* — then proceed.

**2. Extract the story file(s).**
- Take every Jira-story filename in the message (comma- or space-separated).
  Accept them with or without the `.txt` extension and in any case —
  `PROJ-123.TXT`, `PROJ-123.txt`, and `PROJ-123` all mean the same file.
- Normalize each to the real filename under `jira-stories/` (call
  `list_stories` if you need to confirm exact casing). These are the **raw**
  input stories — never the generated `-surgical.txt` / `-connectors.md`.
- If a named story file does not exist under `jira-stories/`, stop and tell
  the user exactly which one is missing.

**3. (UPDATE only) Resolve the target diagram.**
- If the message names a `.drawio` file, use it.
- Otherwise call `list_diagrams` and match by Jira key (story `PROJ-123` →
  diagrams whose name starts with `PROJ-123-`):
  - **Exactly one match** → use it.
  - **No match** → tell the user there is no existing diagram for that key
    and offer to run the CREATE flow instead.
  - **Several matches** → list them and ask which one to update.

**4. Expand to the full backend flow and execute it as-is.**
Open the matching prompt file in this repo and follow it end-to-end exactly
as if the user had pasted it:
- **CREATE, one story** → follow [`prompts/create-diagram.md`](../prompts/create-diagram.md)
  (the single-story body between the `COPY FROM HERE` / `STOP COPYING HERE`
  markers), substituting `{{STORY_FILE}}` with the resolved filename.
- **CREATE, multiple stories** → follow `prompts/create-diagram.md`, but
  apply it to **exactly the listed stories** (not "every story in
  `jira-stories/`"): normalize each, `read_story` each `-surgical.txt`,
  synthesise the combined component/flow set across all of them, then call
  `create_diagram` **once** with `jira_key` set to the lowest key in the batch.
- **UPDATE, one story** → follow [`prompts/update-diagram.md`](../prompts/update-diagram.md)
  (single-story body), substituting `{{STORY_FILE}}` and `{{DIAGRAM_FILE}}`.
- **UPDATE, multiple stories** → follow the multi-story flow in
  `prompts/update-diagram.md` against the resolved diagram, applying exactly
  the listed stories in natural-ascending key order.

Echo your interpretation in one line before the first mutating call — e.g.
*"Interpreting: CREATE a new diagram from PROJ-123.txt — normalizing now."*
Then proceed. (UPDATE still pauses for plan approval per `update-diagram.md`
step 3.) Whichever flow you run, the **Restricted-service guardrail** below
is mandatory before any node is written.

## Restricted-service guardrail (run BEFORE writing any diagram)

> ⛔ **HARD MANDATE — do not skip, ever.** You MUST open and read
> [`policy/unavailable_services.md`](../policy/unavailable_services.md) and
> run this check **before the first `create_diagram` / `add_container` /
> `add_node` / `add_edge` call** in every create or update flow. Building a
> diagram without having run the guardrail, or placing a restricted service
> without the user's **explicit** replacement choice, is a defect — not a
> shortcut. If any planned component is restricted, you must **stop, present
> every candidate replacement, and WAIT for the user to pick** before you
> create anything. Do not assume, do not pick for them, do not proceed on
> "it's probably fine".

Some cloud services are **not allowed** in diagrams produced by this repo.
The disallowed list lives in
[`policy/unavailable_services.md`](../policy/unavailable_services.md). This
gate runs in **both** the create and update flows, **after** you have
identified the components implied by the story and **before** you write any
node (i.e. before `create_diagram` in the create flow, and as part of the
change plan in the update flow).

**Procedure — every time, no exceptions:**

1. **Read** `policy/unavailable_services.md` and build the set of
   restricted service names (include each entry's **Aliases**).
2. **Check** every planned component — its label AND the `gcp_icon` you
   intend to use — against that set. Matching is **case / space /
   underscore-insensitive** (`Cloud Functions` = `cloud_functions` =
   `CLOUDFUNCTIONS`), and matches on the restricted name or any alias.
3. **If nothing matches → proceed silently.** This gate is invisible for a
   compliant design; do not mention it.
4. **If one or more planned components match a restricted service:**
   - Do **not** create, place, or write a node for the restricted service.
   - Gather alternatives **only** from the **Service alternatives
     reference** table in `policy/unavailable_services.md` — the restricted
     list itself carries no alternatives:
     1. Look the matched service up in that table; its
        `alternate1`–`alternate4` are the candidates. **Use the Jira story
        scenario** (data volume, latency, batch vs. streaming, statefulness,
        compliance, components already chosen) to **rank those four** and
        recommend the best fit, with a one-line reason.
     2. Only if the matched service has no row at all in that table, propose
        2–3 similar in-scope services from your own knowledge.
   - **Drop any candidate that is itself restricted** (check every
     candidate against the restricted list, alias-aware) — both reference-
     table entries and own-knowledge fallbacks alike. Skip a restricted
     candidate and take the next one; if all four table candidates are
     restricted, keep going down the chain (alternates of the adjacent
     allowed services in the same reference table) until you have **only
     non-restricted** options. Never present a restricted service as
     an alternative. If no allowed replacement exists, say so and ask the
     user how to proceed.
   - **Ask the user to choose**, in one clear prompt. List each restricted
     service with its numbered candidate alternatives (best fit first), e.g.:

         "Cloud Functions (1st gen)" is restricted by policy. Pick a
         replacement:
           1. Cloud Run
           2. Cloud Functions (2nd gen)
         (reply with a number, or name another approved service)

   - **STOP and wait** for the user's selection. Do not continue the flow,
     create the diagram, or add any node until they reply.
   - Once they choose, substitute the approved service (label + `gcp_icon`)
     into your plan and proceed with the rest of the flow as normal.
5. **Never** silently place a restricted service, and **never** silently
   pick an alternative on the user's behalf. The substitution is always the
   user's explicit choice.

If multiple restricted services are detected, list them all in a single
prompt (one numbered option group per restricted service) so the user makes
all choices at once, then proceed.

## Decision flow

If the user used the **Quick-command shorthand** above, the action and inputs
are already decided — jump straight to the matching prompt flow. Otherwise,
fall back to the general flow:

1. **Read the requirement.** If the user attached a story file path under
   `jira-stories/`, call `read_story` with that filename. If they pasted the
   story directly into chat, use that text.
2. **Survey existing diagrams.** Call `list_diagrams`, then
   `read_diagram_summary` on any candidate diagram(s) to understand current
   topology before proposing changes.
3. **Decide: create vs. update.**
   - If no diagram covers the affected area → `create_diagram`, then add nodes
     and edges.
   - If an existing diagram covers it → patch it with `add_node`,
     `add_edge`, `update_node`, `remove_element`.
4. **Make the change in small steps.** One node or edge per tool call. Do not
   emit a flurry of edits without re-reading the summary if you lose track.
5. **Confirm.** End with a one-line list of what you added / changed / removed
   and the absolute path of the saved file.

## Shape conventions

| Component type | Shape |
|---|---|
| Service / API / microservice | `rounded` or `process` |
| Database (SQL / NoSQL) | `cylinder` |
| Message broker / queue / topic | `queue` |
| End user / persona | `actor` |
| External SaaS / third party | `cloud` |
| Logical grouping (e.g. "AWS VPC") | `container` |

**GCP services use icons, not stencils (mandatory).** When a node
represents a Google Cloud service — Cloud Run, Cloud Functions, App
Engine, Compute Engine, GKE, BigQuery, Cloud SQL, Cloud Spanner,
Bigtable, Firestore, Memorystore, Cloud Storage, Pub/Sub, Dataflow,
Dataproc, Vertex AI, Apigee, Cloud Load Balancing, Cloud CDN, Cloud
Armor, IAM, Secret Manager, KMS, Cloud Logging, Cloud Monitoring,
Cloud Build, Artifact Registry, and the rest of GCP — pass
`gcp_icon="<service name>"` to `add_node` / `update_node`. **Do not**
use `shape=rounded/rectangle/cylinder` for these. The server resolves
the SVG, inlines it as a URL-encoded data URI, and defaults size to
64×64. Accepted forms are case/space/underscore-insensitive:
`"BigQuery"`, `"bigquery"`, `"big query"`, `"Cloud SQL"`, `"cloud_sql"`,
`"pubsub"`, `"GKE"`, `"Vertex AI"`, etc.

Safety net: if you forget `gcp_icon` and the label clearly names a GCP
service, the server auto-detects and applies the icon, returning
`auto_detected_gcp_icon` in the response. Prefer being explicit so the
choice is visible in the tool call.

Before declaring the diagram complete, re-scan your `add_node` calls:
any GCP service label that wasn't created with `gcp_icon` and wasn't
auto-detected must be fixed with `update_node(..., gcp_icon=...)`. A
diagram of plain grey rectangles labelled "Cloud Run" / "BigQuery" is
considered broken.

Edge labels should describe the **relationship**, not the protocol detail
unless the protocol is the point: `publishes order events`, `reads`,
`HTTPS`, `JDBC`.

## Layout — swimlanes first, then nodes

Architecture diagrams in this repo are **layered**: every node sits
inside a labeled swimlane (External / Ingestion / Processing /
Staging / Curation / Observability — pick the relevant subset).

1. Call `add_container` 4–6 times BEFORE any `add_node`, one per
   architectural layer, with a `color_hint` from the curated palette
   (`external`, `ingestion`, `processing`, `staging`, `curation`,
   `serving`, `observability`, `security`). The server lays them out
   left-to-right with **140-px column gaps** — wide enough that the
   orthogonal edge router has a full corridor between every pair of
   containers and busy-node card borders never touch a neighbour.
2. Call `add_node(..., parent_id=<container_id>, gcp_icon=...)` per
   component, nesting it inside the right swimlane. The server
   auto-stacks children vertically with a **200-px row stride** —
   leaves a ~136-px clear lane between adjacent icons so the
   orthogonal edge router can fan up to ~7 stacked connector labels
   in one row-gap without overlapping each other or the icon-name
   label of the row above.
3. Call `add_edge` per connection. Each call auto-assigns a 1-based
   step number rendered as a `"N. <label>"` prefix on the edge
   label, fans out parallel edges (same source/target) by spreading
   exit/entry fractions, and computes explicit waypoints that route
   cross-container edges through known-empty row gaps so they
   never draw over an icon.

`add_node` only falls back to the 4-column wrap grid for top-level
nodes (no `parent_id`) — that path is for legends and one-off
floating nodes, not for normal components.

## Connector-details table — ALWAYS FILL, never ship with {TBD}

After every `add_edge` mutation is complete (and `verify_mcp.py`
exits 0), TWO documentation artifacts must be produced:

1. **`jira-stories/<KEY>-connectors.md`** — a markdown table with
   one row per numbered connector and 14 columns. Generated by
   `python scripts/generate_connector_details.py --diagram <FILE>
   --story <KEY>-surgical.txt`. The generator emits `{TBD}` for
   every detail cell on first run.

2. **An embedded table inside the .drawio file** — built by the
   `add_connector_table` MCP tool. Reads the .md and threads each
   row's values into 253 cells positioned below the swimlanes.

**Auto-fill is the default**: when `ANTHROPIC_API_KEY` is set, the
generator script (`scripts/generate_connector_details.py`) calls
Claude with the surgical story + schema + skeleton and writes the
**fully filled** `<KEY>-connectors.md` directly. You don't have to
edit it manually — the file is already populated by the time the
script exits 0.

**Delegate fill path** (when no API key / SDK): the script exits 2
with a `NEEDS_FILL` JSON payload containing the schema, surgical
story, and skeleton. In this case YOU — the conversational LLM
running the prompt — MUST replace every `{TBD}` in the file via
your Write tool BEFORE calling `add_connector_table`. The
`add_connector_table` MCP tool has a hard pre-flight guard that
**refuses to embed** if ANY `{TBD}` token (plain or qualified)
is found — zero tolerance. You'll get an error, not a silent
placeholder-only table.

Whether the auto-fill or delegate path runs, the filling rule is the
same:

- **The surgical story** as the primary source. Section 3 (In Scope)
  names components and connections — derive interaction patterns,
  protocols, data formats, etc. from that prose.
- **GCP architectural defaults** for named services. A connector
  involving `Cloud Storage` uses HTTPS REST, port 443, Service
  Account auth, TLS 1.3 in transit, Google-managed CMEK at rest,
  no special PII handling unless the story says so. A `Pub/Sub`
  topic is event-driven, at-least-once delivery, JSON or Avro
  payload, IAM-scoped subscribers. Etc.
- **Reasonable engineering inference** for non-controversial choices.
  Idempotency, retry-with-backoff, structured logs going to Cloud
  Logging, Cloud Monitoring metrics, P95 latency budgets in the
  hundreds of ms — these are sensible defaults a reviewer can
  accept or override.

**ZERO `{TBD}` of any form in the deliverable.** For
business-decision fields (residency, compliance scope, peak TPS,
team ownership, dollar budgets), output a **sensible default
labelled `(assumed)` or `(default)`** — never a `{TBD}` placeholder.
Examples:
- `Reg scope: SOC 2 + GDPR (assumed for EU-origin data)` ← good
- `Residency: us-central1 only (default; confirm with data-residency policy)` ← good
- `PCI/HIPAA: Out of scope (assumed; legal review for sensitive datasets)` ← good
- `Reg scope: {TBD: GDPR if EU-origin data}` ← REJECTED by pre-flight guard

The `(assumed)` / `(default)` label signals "this is a default that
needs confirmation" while keeping the table free of placeholder
syntax. The reviewer can override; the deliverable stays concrete.

The detail schema (per column, what sub-fields belong in each cell)
lives in [`docs/connector-details-template.md`](../docs/connector-details-template.md).
Read that file before filling a row; it tells you the exact shape
each cell should follow (e.g. AuthN/Z cells follow
`AuthN: <method>; AuthZ: <model>; Issuer: <who>; TTL: <duration>;
Secret store: <where>`).

After you've filled every cell, run `add_connector_table` — the
embedded diagram table picks up your filled values automatically.
A reviewer opening the .drawio file then sees both the architecture
AND the integration contract per connector in one place.

## What not to do

- Don't read or write files outside `diagrams/` and `jira-stories/`.
- Don't invent components that aren't in the story or already in the diagram.
- Don't rewrite a diagram from scratch when a small patch will do — that
  destroys the user's manual layout work.
- **Don't deliver a diagram with `{TBD}` cells in the connector
  table.** The table is data, not a checklist of open questions —
  fill it in using the sources above before declaring done.
