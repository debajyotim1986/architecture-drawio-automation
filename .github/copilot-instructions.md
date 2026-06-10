# Copilot instructions — architecture diagram assistant

You are helping the user maintain `.drawio` architecture diagrams for this
repository. The user will attach (or point to) a downloaded **Jira story
summary** and ask you to either **create** or **update** an architecture
diagram so it reflects the requirement in that story.

You have access to the `drawio` MCP server. Use **only** its tools to read
and write `.drawio` files — never hand-edit the XML.

## Decision flow

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
