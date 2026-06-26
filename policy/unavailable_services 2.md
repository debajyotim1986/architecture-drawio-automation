# Unavailable / Restricted Services

**Single source of truth for cloud services that are NOT allowed** in any
architecture diagram generated in this repo. Edit this file to match your
organisation's cloud-governance policy — it is read automatically before
every diagram is written.

> ⚠️ The entries below are **starter examples**. Replace them with the
> services your org actually disallows. Anything listed here will be
> blocked from appearing in a diagram; the assistant will offer an allowed
> alternative from the Service alternatives reference and ask you to choose
> before continuing.

---

## How this file is used

Before writing any diagram (create **or** update), the assistant:

1. Reads this file and builds the set of restricted service names.
2. Checks every **planned component** — its label and its chosen
   `gcp_icon` — against that set.
3. If a planned component matches a restricted service, the assistant
   **does not place it**. Instead it pulls candidate replacements from the
   [Service alternatives reference](#service-alternatives-reference) table,
   ranks them for the scenario, and **asks you to pick one** before
   continuing. Nothing is written until you choose.

If no planned component matches anything here, the flow proceeds silently —
this gate is invisible when the design is already compliant.

## Matching rules

- Matching is **case / space / underscore-insensitive**:
  `Cloud Functions`, `cloud_functions`, and `CLOUDFUNCTIONS` all match the
  same entry.
- An entry matches if the restricted name (or any of its **aliases**)
  appears in a node label or in the `gcp_icon` value chosen for that node.
- List the broad service name plus enough aliases to catch every way it can
  be written or chosen as a `gcp_icon`. Restricting `Cloud Functions` (with
  its aliases) blocks **every** Cloud Functions node regardless of variant.

### Service alternatives reference

For every supported GCP service, this table lists up to four candidate
replacements (`alternate1`–`alternate4`) that perform a similar function.
**When a service appears in the [Restricted services](#restricted-services)
list below, the assistant looks it up here, then uses the Jira story
scenario to pick the best-fitting alternate** — and asks you to confirm
before writing anything (see [How alternatives are chosen](#how-alternatives-are-chosen)).

Edit any row to match what your platform actually approves. The order of
the columns carries no ranking — the LLM ranks them per scenario.

| GCP service | alternate1 | alternate2 | alternate3 | alternate4 |
|---|---|---|---|---|
| App Engine | Cloud Run | GKE | Compute Engine | Cloud Functions |
| Batch | Dataproc | Compute Engine | GKE | Cloud Run |
| Cloud Functions | Cloud Run | App Engine | GKE | Compute Engine |
| Cloud Run | Cloud Functions | App Engine | GKE | Compute Engine |
| Cloud TPU | Cloud GPU | Vertex AI | Compute Engine | GKE |
| Compute Engine | GKE | Cloud Run | App Engine | Anthos |
| GKE | Cloud Run | Anthos | Compute Engine | App Engine |
| Anthos | GKE | Compute Engine | Cloud Run | Traffic Director |
| AlloyDB | Cloud SQL | Cloud Spanner | Bigtable | Firestore |
| BigQuery | Cloud Spanner | Bigtable | Dataproc | AlloyDB |
| Bigtable | Firestore | Cloud Spanner | Memorystore | BigQuery |
| Cloud SQL | AlloyDB | Cloud Spanner | Bigtable | Firestore |
| Cloud Spanner | AlloyDB | Cloud SQL | Bigtable | Firestore |
| Datastore | Firestore | Bigtable | Cloud SQL | Memorystore |
| Firestore | Datastore | Bigtable | Cloud SQL | Memorystore |
| Memorystore | Bigtable | Firestore | Cloud SQL | Cloud Spanner |
| Cloud Storage | Filestore | Persistent Disk | Bigtable | BigQuery |
| Filestore | Cloud Storage | Persistent Disk | Memorystore | Bigtable |
| Persistent Disk | Filestore | Local SSD | Hyperdisk | Cloud Storage |
| Cloud Composer | Workflows | Cloud Scheduler | Dataflow | Cloud Tasks |
| Cloud Scheduler | Cloud Tasks | Workflows | Cloud Composer | Eventarc |
| Cloud Tasks | Pub/Sub | Cloud Scheduler | Workflows | Eventarc |
| Data Fusion | Dataflow | Dataproc | Cloud Composer | Datastream |
| Dataflow | Dataproc | Cloud Composer | Data Fusion | BigQuery |
| Dataproc | Dataflow | Cloud Composer | Data Fusion | Batch |
| Datastream | Data Fusion | Dataflow | Pub/Sub | Dataproc |
| Eventarc | Pub/Sub | Cloud Tasks | Workflows | Cloud Scheduler |
| Pub/Sub | Eventarc | Cloud Tasks | Dataflow | Workflows |
| Workflows | Cloud Composer | Cloud Tasks | Eventarc | Cloud Scheduler |
| AutoML | Vertex AI | Document AI | Dialogflow | Cloud TPU |
| Dialogflow | Vertex AI | Agent Assist | Document AI | AutoML |
| Document AI | Vertex AI | AutoML | Cloud Translation API | Dialogflow |
| Vertex AI | AutoML | Document AI | Dialogflow | Cloud TPU |
| API Gateway | Apigee | Cloud Load Balancing | Cloud Armor | Cloud CDN |
| Apigee | API Gateway | Cloud Load Balancing | Cloud CDN | Cloud Armor |
| Cloud Armor | Cloud Load Balancing | Cloud CDN | Identity-Aware Proxy | Cloud NAT |
| Cloud CDN | Cloud Load Balancing | Cloud Armor | Cloud Storage | Apigee |
| Cloud DNS | Cloud Load Balancing | VPC | Cloud NAT | Cloud CDN |
| Cloud Load Balancing | Cloud CDN | Traffic Director | Cloud Armor | Cloud DNS |
| Cloud NAT | Cloud VPN | Cloud Interconnect | VPC | Cloud DNS |
| Cloud VPN | Cloud Interconnect | Cloud NAT | VPC | Traffic Director |
| IAM | Identity Platform | Identity-Aware Proxy | Secret Manager | KMS |
| Identity Platform | IAM | Identity-Aware Proxy | Secret Manager | KMS |
| KMS | Cloud EKM | Secret Manager | Certificate Manager | IAM |
| Secret Manager | KMS | Cloud EKM | IAM | Identity Platform |
| VPC | Cloud NAT | Cloud VPN | Cloud Interconnect | Cloud DNS |
| Cloud Logging | Cloud Monitoring | Cloud Trace | Error Reporting | Stackdriver |
| Cloud Monitoring | Cloud Logging | Cloud Trace | Error Reporting | Stackdriver |
| Cloud Trace | Cloud Monitoring | Cloud Logging | Error Reporting | Stackdriver |
| Error Reporting | Cloud Logging | Cloud Monitoring | Cloud Trace | Stackdriver |
| Artifact Registry | Container Registry | Cloud Build | Cloud Storage | Cloud Deploy |
| Cloud Build | Cloud Deploy | Artifact Registry | Container Registry | GKE |
| Cloud Deploy | Cloud Build | Artifact Registry | GKE | Cloud Run |
| Container Registry | Artifact Registry | Cloud Build | Cloud Storage | Cloud Deploy |
| Vertex AI Agent Engine | Vertex AI Agent Builder | Dialogflow CX | Vertex AI | Cloud Run |
| Vertex AI Agent Builder | Vertex AI Agent Engine | Vertex AI Search | Dialogflow CX | Vertex AI |
| Gemini | Vertex AI | Vertex AI Studio | Model Garden | AutoML |
| Vertex AI Studio | Vertex AI | Gemini | Model Garden | AutoML |
| Model Garden | Vertex AI | Gemini | Vertex AI Studio | AutoML |
| Vertex AI Search | Vertex AI Agent Builder | Vector Search | Recommendations AI | Vertex AI |
| Vector Search | Vertex AI Search | AlloyDB | Firestore | Bigtable |
| Vertex AI Pipelines | Vertex AI | Cloud Composer | Kubeflow | Dataflow |
| Vertex AI Feature Store | Bigtable | Firestore | BigQuery | Vertex AI |
| Dialogflow CX | Dialogflow | Vertex AI Agent Builder | Contact Center AI | Vertex AI Agent Engine |
| Contact Center AI | Dialogflow CX | Agent Assist | Dialogflow | Vertex AI |
| Agent Assist | Contact Center AI | Dialogflow CX | Dialogflow | Vertex AI |
| Speech-to-Text | Vertex AI | Contact Center AI | AutoML | Dialogflow |
| Text-to-Speech | Vertex AI | Contact Center AI | Dialogflow | AutoML |
| Cloud Translation API | Vertex AI | AutoML | Document AI | Gemini |
| Cloud Vision API | Document AI | Vertex AI | AutoML | Gemini |
| Cloud Natural Language API | Vertex AI | Document AI | AutoML | Gemini |
| Recommendations AI | Vertex AI Search | Vertex AI | Vertex AI Agent Builder | AutoML |
| Looker | Looker Studio | BigQuery | Dataplex | Data Catalog |
| Looker Studio | Looker | BigQuery | Dataplex | Vertex AI |
| Dataplex | Data Catalog | BigQuery | Dataproc | Data Fusion |
| Data Catalog | Dataplex | BigQuery | Data Fusion | Dataproc |
| BigLake | BigQuery | Cloud Storage | Dataplex | Dataproc |
| Cloud Run Jobs | Cloud Run | Batch | Cloud Functions | GKE |
| Bare Metal Solution | Compute Engine | VMware Engine | GKE | Anthos |
| VMware Engine | Compute Engine | Bare Metal Solution | GKE | Anthos |
| Cloud Interconnect | Cloud VPN | Network Connectivity Center | Cloud Router | VPC |
| Cloud Service Mesh | Traffic Director | Anthos | GKE | Cloud Load Balancing |
| Traffic Director | Cloud Service Mesh | Cloud Load Balancing | Anthos | GKE |
| Network Connectivity Center | Cloud Interconnect | Cloud VPN | Cloud Router | VPC |
| Identity-Aware Proxy | Access Context Manager | IAM | Cloud Armor | Cloud Load Balancing |
| Cloud Endpoints | API Gateway | Apigee | Cloud Load Balancing | Cloud Armor |
| Security Command Center | Cloud Armor | IAM | Cloud Logging | Sensitive Data Protection |
| VPC Service Controls | Access Context Manager | IAM | VPC | Cloud Armor |
| Access Context Manager | VPC Service Controls | IAM | Identity-Aware Proxy | Cloud Armor |
| Certificate Manager | KMS | Secret Manager | Cloud Load Balancing | Cloud Armor |
| Cloud EKM | KMS | Secret Manager | Certificate Manager | IAM |
| Sensitive Data Protection | IAM | KMS | Security Command Center | Cloud Armor |
| Cloud Source Repositories | Artifact Registry | Cloud Build | Cloud Deploy | Container Registry |
| Cloud Workstations | Compute Engine | GKE | Cloud Run | Cloud Shell |

## How alternatives are chosen

The [Restricted services](#restricted-services) list only declares *what is
banned*. **Every replacement comes from the
[Service alternatives reference](#service-alternatives-reference) table — and
from nowhere else.** When a planned component matches a restricted service,
the assistant:

1. **Looks it up in the Service alternatives reference** table and takes its
   `alternate1`–`alternate4` as the candidate replacements.
2. **Ranks those candidates for the Jira story scenario** (data volumes,
   latency, statefulness, streaming vs. batch, compliance, existing
   components, etc.), recommending the best fit and noting why.
3. **Own knowledge — fallback only.** Only if the restricted service has no
   row at all in the alternatives table does the assistant propose 2–3
   similar in-scope services from its own knowledge.

**Never offer a restricted service as an alternative.** Before presenting
any candidate, drop every option that is itself in the
[Restricted services](#restricted-services) list (alias-aware). If a
candidate is restricted, skip it and take the next one. If **all** of a
service's table candidates are restricted, keep going down the chain —
evaluate the alternates *of the allowed adjacent services* in the same
reference table — until you reach services that are allowed. Only ever show
the user services that are **not** restricted; if a scenario genuinely has
no allowed replacement, say so and ask the user how to proceed rather than
offering a banned service.

**In every case the assistant presents only allowed candidates and asks you
to confirm which one to use — it never silently substitutes**, and it never
places the restricted service itself.

---

## Restricted services

This table only declares **what is banned** — just the service name and any
aliases. Replacements are **always** taken from the
[Service alternatives reference](#service-alternatives-reference) table
above; this table intentionally carries no reason or alternatives column.

| service name | aliases |
|---|---|
| Container Registry | gcr, container_registry |
| Cloud Functions | cloud function, cloudfunctions, cloud_functions, gcf, cloud functions 1st gen, cloud functions 2nd gen |
| Datastore | cloud datastore, datastore mode |
| Cloud SQL | cloudsql |

<!--
Add rows in the same shape — just the service name and any aliases.
The replacement is always chosen from the Service alternatives reference
table, never declared here, e.g.:

| Dialogflow ES | dialogflow es |
-->
