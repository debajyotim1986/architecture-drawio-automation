#!/usr/bin/env python3
"""Generate the per-connector documentation table for a diagram.

Reads a `.drawio` file, iterates its edges in step-number order, and
writes a markdown table at `jira-stories/<KEY>-connectors.md` with
one row per numbered edge. Columns match the boilerplate schema in
`docs/connector-details-template.md`; values default to `{TBD}` so
a downstream LLM (or human reviewer) fills them in.

Cross-platform — same self-bootstrap pattern as
`normalize_jira_story.py` and `verify_mcp.py`. A single
`python scripts/generate_connector_details.py ...` command works on
macOS, Linux, and Windows.

Typical use (from the create-diagram prompt):

    python scripts/generate_connector_details.py \
        --diagram diagrams/PROJ-126-YYYYMMDD-HHMMSS.drawio \
        --story  jira-stories/PROJ-126-surgical.txt

Exit codes:
    0  Table written successfully.
    1  Hard error (file missing, diagram has no edges, etc.).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIAGRAMS_DIR = REPO_ROOT / "diagrams"
DEFAULT_STORIES_DIR = REPO_ROOT / "jira-stories"
DEFAULT_TEMPLATE_DOC = REPO_ROOT / "docs" / "connector-details-template.md"
MCP_SRC = REPO_ROOT / "drawio-mcp-server" / "src"
if MCP_SRC.exists() and str(MCP_SRC) not in sys.path:
    sys.path.insert(0, str(MCP_SRC))

MODEL_DEFAULT = "claude-sonnet-4-6"

# How many `{TBD}` cells (of ANY form — plain `{TBD}` OR qualified
# `{TBD: <hint>}`) we tolerate in the final filled output. Zero
# tolerance: the Always-Fill rule says every cell must carry a
# concrete value, with `(assumed)` / `(default)` markers used in
# place of placeholders for business-decision fields.
_MAX_ANY_TBD = 0


def _maybe_reexec_under_venv() -> None:
    """Same self-bootstrap as the other Python scripts in scripts/."""
    if os.environ.get("_GENCONN_VENV_BOOTSTRAPPED"):
        return
    if sys.platform == "win32":
        venv_py = REPO_ROOT / "drawio-mcp-server" / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = REPO_ROOT / "drawio-mcp-server" / ".venv" / "bin" / "python"
    if not venv_py.exists():
        return
    try:
        same = Path(sys.executable).resolve() == venv_py.resolve()
    except (OSError, RuntimeError):
        same = False
    if same:
        return
    new_env = dict(os.environ)
    new_env["_GENCONN_VENV_BOOTSTRAPPED"] = "1"
    argv = [str(venv_py), str(Path(__file__).resolve()), *sys.argv[1:]]
    if sys.platform == "win32":
        import subprocess
        sys.exit(subprocess.run(argv, env=new_env).returncode)
    else:
        os.execve(str(venv_py), argv, new_env)


_maybe_reexec_under_venv()


# Column schema — KEEP IN SYNC WITH docs/connector-details-template.md
COLUMNS: list[tuple[str, str]] = [
    # (header,                            default cell value)
    ("Step",                              ""),    # filled per-row
    ("Source",                            ""),    # filled per-row
    ("Target",                            ""),    # filled per-row
    ("Action",                            ""),    # filled per-row
    # Detail columns — filled by the rule engine (`_rule_fill_row`)
    # so the output NEVER contains `{TBD}` regardless of whether the
    # LLM step runs.
    ("Interaction Pattern",               ""),
    ("Protocol & API",                    ""),
    ("AuthN & AuthZ",                     ""),
    ("Data",                              ""),
    ("Network & Connectivity",            ""),
    ("Performance & SLA",                 ""),
    ("Reliability & Resilience",          ""),
    ("Observability",                     ""),
    ("Compliance & Governance",           ""),
    ("Dependencies & Failure Mode",       ""),
]


# =============================================================================
# Deterministic rule-based fill engine
# =============================================================================
#
# Given (source_label, target_label, action_label), produce a concrete value
# for each of the 10 detail columns using a GCP-defaults rule set.
#
# This runs UNCONDITIONALLY before the file is written, so the output never
# contains `{TBD}` even when the optional LLM refinement (--fill auto) is
# unavailable. Cells that genuinely need business confirmation use the
# `(default)` / `(assumed)` marker convention instead of placeholders.

_SERVICE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    # Order matters: more specific patterns first.
    ("dataplex",          ("dataplex",)),
    ("composer_sensor",   ("composer sensor", "sensor")),
    ("composer",          ("composer", "airflow", "orchestrator")),
    ("dataproc",          ("dataproc",)),
    ("pubsub",            ("pub/sub", "pubsub", "pub sub")),
    ("bigquery_audit",    ("bigquery audit", "bq audit", "audit")),
    ("bigquery_curation", ("bigquery curation", "bq curation", "curation")),
    ("bigquery_staging",  ("bigquery staging", "bq staging", "staging")),
    ("bigquery",          ("bigquery", "bq")),
    ("gcs",               ("gcs", "cloud storage", "landing")),
    ("cloud_logging",     ("cloud logging", "logging")),
    ("cloud_monitoring",  ("cloud monitoring", "monitoring")),
    ("cloud_run",         ("cloud run",)),
    ("cloud_functions",   ("cloud function", "function")),
    ("secret_manager",    ("secret manager",)),
    ("on_prem",           ("on-prem", "on prem", "onprem", "upstream", "external", "source")),
]


def _service_type(label: str) -> str:
    """Identify a GCP / external service type from a node label."""
    lbl = (label or "").lower()
    for service, words in _SERVICE_PATTERNS:
        for w in words:
            if w in lbl:
                return service
    return "unknown"


def _action_type(action: str) -> str:
    a = (action or "").lower()
    if "log" in a:
        return "logs"
    if "metric" in a:
        return "metrics"
    if "object event" in a or "event" in a:
        return "event"
    if "trigger" in a:
        return "triggers"
    if "poll" in a or "5 min" in a or "polled" in a:
        return "poll"
    if "manage" in a or "create" in a:
        return "manages"
    if "upload" in a:
        return "uploads"
    if "write" in a or "load" in a:
        return "writes"
    if "read" in a:
        return "reads"
    if "validat" in a:
        return "validates"
    if "audit" in a:
        return "audit"
    return "default"


def _rule_interaction(src: str, tgt: str, act: str) -> str:
    if act in ("logs", "metrics"):
        return "Asynchronous; Streaming; Push; One-way (fire & forget)"
    if act == "event":
        return "Asynchronous; Event-Driven; Push; One-way"
    if act == "triggers":
        return "Asynchronous; Event-Driven; Push; One-way"
    if act == "poll":
        return "Asynchronous; Batch (scheduled poll); Pull; One-way"
    if act == "manages":
        return "Synchronous; Request-Response; Push; Two-way"
    if act in ("uploads", "writes"):
        return "Asynchronous; Batch; Push; One-way"
    if act == "reads":
        return "Synchronous; Request-Response; Pull; Two-way"
    if act == "validates":
        return "Asynchronous; Batch (scheduled scan); Pull; Two-way"
    if act == "audit":
        return "Synchronous; Request-Response; Push; Two-way"
    return "Asynchronous; Batch; Push; One-way (default — confirm with architect)"


def _rule_protocol(src: str, tgt: str, act: str) -> str:
    if tgt == "gcs" and act == "uploads":
        return "HTTPS; REST (GCS JSON API); 443; v1; gs://<bucket>/<path>; PUT/POST; JSON manifest"
    if tgt == "pubsub" or act == "event":
        return "Pub/Sub (GCP); Event; n/a (managed); v1; topic projects/<p>/topics/<topic>; publish; CloudEvents 1.0 JSON"
    if tgt == "cloud_logging" or act == "logs":
        return "gRPC over HTTPS (Cloud Logging API); RPC; 443; v2; projects/<p>/logs/<name>; WriteLogEntries; Protobuf"
    if tgt == "cloud_monitoring" or act == "metrics":
        return "gRPC over HTTPS (Cloud Monitoring API); RPC; 443; v3; projects/<p>/timeSeries; CreateTimeSeries; Protobuf"
    if tgt.startswith("bigquery") and act in ("writes", "uploads", "audit"):
        return "BigQuery Storage Write API; gRPC over HTTPS; 443; v1; projects/<p>/datasets/<d>/tables/<t>; AppendRows / Load; Protobuf or Avro"
    if src.startswith("bigquery") and act == "reads":
        return "BigQuery Storage Read API; gRPC over HTTPS; 443; v1; projects/<p>/datasets/<d>/tables/<t>; CreateReadSession + ReadRows; Arrow IPC"
    if tgt == "dataproc" and act == "manages":
        return "gRPC over HTTPS (Dataproc API); RPC; 443; v1; projects/<p>/regions/<r>/clusters; CreateCluster / DeleteCluster / SubmitJob; Protobuf"
    if tgt == "composer" and (src == "pubsub" or act == "triggers"):
        return "HTTPS (Pub/Sub push subscription); REST; 443; v1; Composer webhook /trigger/<dag_id>; POST; CloudEvents JSON + run_id"
    if src == "composer_sensor" and tgt == "composer":
        return "Composer-internal DAG-to-DAG (TriggerDagRunOperator); RPC; n/a (in-cluster); n/a; n/a; n/a; Airflow XCom"
    if src == "gcs" and act == "poll":
        return "HTTPS; REST (GCS LIST objects); 443; v1; gs://<bucket>/<prefix>/*; GET; JSON"
    if tgt == "dataplex" or act == "validates":
        return "Dataplex Data Quality scan API; gRPC over HTTPS; 443; v1; projects/<p>/locations/<r>/lakes/<l>/dataQualityScans/<scan>; RunScan; Protobuf"
    return "HTTPS; REST; 443; v1; <endpoint>; <methods> (default GCP API — confirm endpoint)"


def _rule_auth(src: str, tgt: str, act: str) -> str:
    if src == "on_prem":
        return (
            "AuthN: Service Account (GCP) via short-lived OAuth2 from on-prem WIF; "
            "AuthZ: roles/storage.objectCreator (or service-specific); "
            "Issuer: project-sa@<project>.iam.gserviceaccount.com; "
            "TTL: 1h access token; Secret store: Secret Manager (refresh creds)"
        )
    if src == "pubsub" and tgt == "composer":
        return (
            "AuthN: OIDC token (Pub/Sub push-managed SA); "
            "AuthZ: roles/composer.user; "
            "Issuer: pubsub-push-sa@<project>.iam.gserviceaccount.com; "
            "TTL: 1h OIDC; Secret store: managed by Pub/Sub"
        )
    if src == "composer" and tgt == "dataproc":
        return (
            "AuthN: Composer worker SA (Workload Identity); "
            "AuthZ: roles/dataproc.editor; "
            "Issuer: composer-sa@<project>; TTL: 1h; "
            "Secret store: Workload Identity (no key file)"
        )
    if src == "dataproc" and tgt.startswith("bigquery"):
        suffix = tgt.replace("bigquery_", "") if "_" in tgt else "default"
        role = {
            "staging": "roles/bigquery.dataEditor (staging) + bigquery.jobUser",
            "curation": "roles/bigquery.dataEditor (curation only)",
            "audit": "roles/bigquery.dataEditor (audit table only)",
            "default": "roles/bigquery.dataEditor",
        }.get(suffix, "roles/bigquery.dataEditor")
        return (
            f"AuthN: Dataproc cluster SA; AuthZ: {role}; "
            f"Issuer: dataproc-cluster-sa@<project>; TTL: 1h; "
            f"Secret store: Workload Identity"
        )
    if src.startswith("bigquery") and tgt == "dataproc":
        return (
            "AuthN: Dataproc cluster SA; "
            "AuthZ: roles/bigquery.dataViewer + bigquery.readSessionUser; "
            "Issuer: dataproc-cluster-sa@<project>; TTL: 1h; "
            "Secret store: Workload Identity"
        )
    if src == "composer" and tgt.startswith("bigquery"):
        return (
            "AuthN: Composer worker SA; "
            "AuthZ: roles/bigquery.dataEditor (target table only — least privilege); "
            "Issuer: composer-sa@<project>; TTL: 1h; "
            "Secret store: Workload Identity"
        )
    if act == "logs":
        return (
            f"AuthN: {src.replace('_', ' ').title()} SA; "
            f"AuthZ: roles/logging.logWriter; "
            f"Issuer: <service>-sa@<project>; TTL: 1h; "
            f"Secret store: Workload Identity"
        )
    if act == "metrics":
        return (
            f"AuthN: {src.replace('_', ' ').title()} SA; "
            f"AuthZ: roles/monitoring.metricWriter; "
            f"Issuer: <service>-sa@<project>; TTL: 1h; "
            f"Secret store: Workload Identity"
        )
    if tgt == "dataplex" or act == "validates":
        return (
            "AuthN: Dataplex service agent + scan SA; "
            "AuthZ: roles/dataplex.dataReader + roles/bigquery.dataViewer; "
            "Issuer: dataplex-sa@<project>; TTL: 1h; "
            "Secret store: Workload Identity"
        )
    return (
        "AuthN: GCP Service Account (default); "
        "AuthZ: <service-specific role>; "
        "Issuer: <service>-sa@<project>; TTL: 1h; "
        "Secret store: Workload Identity (default)"
    )


def _rule_data(src: str, tgt: str, act: str) -> str:
    if src == "on_prem" and tgt == "gcs":
        return (
            "Format: CSV / Parquet / multi-format per source; "
            "Size: avg 50 MB / max 2 GB; "
            "Classification: Internal; "
            "In-transit: TLS 1.3 (ECDHE-AES256-GCM); "
            "At-rest: Google-managed (CMEK for classified); "
            "Masking: none at landing tier; "
            "Schema evol: per-source (Parquet evolution, CSV header-versioned)"
        )
    if tgt == "pubsub" or act == "event":
        return (
            "Format: JSON CloudEvent; Size: ~1 KB per event; "
            "Classification: Internal; In-transit: TLS 1.3 (managed); "
            "At-rest: Pub/Sub at-rest encryption (Google-managed); "
            "Masking: none; Schema evol: CloudEvents 1.0 backward-compatible"
        )
    if act == "logs":
        return (
            "Format: structured JSON log entries; Size: <10 KB per entry; "
            "Classification: Internal (may reference Confidential — never row data); "
            "In-transit: TLS 1.3; At-rest: Cloud Logging managed; "
            "Masking: row contents stripped at emit per logging-config; "
            "Schema evol: JSON free-form additive"
        )
    if act == "metrics":
        return (
            "Format: time-series points (metric_name, value, timestamp, labels); "
            "Size: ~200 B per point; Classification: Internal (aggregates); "
            "In-transit: TLS 1.3; At-rest: Cloud Monitoring managed; "
            "Masking: aggregates only (no per-row data); "
            "Schema evol: stable metric schema with additive labels"
        )
    if act == "validates":
        return (
            "Format: DQ rule results (rows-checked / passed / failed + sample row hashes); "
            "Size: <1 MB per scan; Classification: Internal (DQ metadata); "
            "In-transit: TLS 1.3; At-rest: Dataplex managed; "
            "Masking: aggregate-only output (no raw values); "
            "Schema evol: Dataplex DQ result schema v1"
        )
    if tgt == "bigquery_curation":
        return (
            "Format: business-modelled records (joined / aggregated / normalized); "
            "Size: avg 100 MB / max 5 GB per write; "
            "Classification: Confidential (downstream consumption); "
            "In-transit: TLS 1.3; At-rest: BQ CMEK (curation tier mandated); "
            "Masking: PII columns hashed SHA-256 or tokenized; "
            "Schema evol: forward-compatible additive only (downstream contract)"
        )
    if tgt == "bigquery_staging":
        return (
            "Format: Parquet (Spark output) → BQ Avro write; "
            "Size: avg 50 MB / max 2 GB per partition; "
            "Classification: Internal (raw); In-transit: TLS 1.3; "
            "At-rest: BQ Google-managed (CMEK for classified); "
            "Masking: none at staging; "
            "Schema evol: BQ schema relaxation (add nullable cols)"
        )
    if tgt == "bigquery_audit":
        return (
            "Format: structured audit record (run_id, source_file, counts, status, duration); "
            "Size: <1 KB per row; Classification: Internal (audit-grade); "
            "In-transit: TLS 1.3; At-rest: BQ CMEK; Masking: none; "
            "Schema evol: additive only (audit contract)"
        )
    if src.startswith("bigquery") and act == "reads":
        return (
            "Format: Arrow IPC (columnar); Size: 1-10 GB per partition; "
            "Classification: Internal; In-transit: TLS 1.3; "
            "At-rest: BQ Google-managed / CMEK; Masking: per-column policies; "
            "Schema evol: handled by Spark schema-merge"
        )
    if tgt == "dataproc" and act == "manages":
        return (
            "Format: Protobuf cluster config + job spec; Size: <100 KB per call; "
            "Classification: Internal; In-transit: TLS 1.3; "
            "At-rest: cluster metadata Google-managed; Masking: none; "
            "Schema evol: Dataproc API backward-compatible"
        )
    if act == "poll":
        return (
            "Format: list of object metadata (name, size, mtime); "
            "Size: <100 KB per poll; Classification: Internal; "
            "In-transit: TLS 1.3; At-rest: n/a (read-only); "
            "Masking: none; Schema evol: GCS API stable v1"
        )
    if act == "triggers":
        return (
            "Format: JSON CloudEvent + run_id (or Airflow trigger payload); "
            "Size: <10 KB; Classification: Internal; In-transit: TLS 1.3; "
            "At-rest: n/a; Masking: none; Schema evol: backward-compatible"
        )
    return (
        "Format: JSON (default); Size: <100 KB per call (default); "
        "Classification: Internal (default); In-transit: TLS 1.3; "
        "At-rest: Google-managed (default); Masking: none; "
        "Schema evol: backward-compatible (default — confirm)"
    )


def _rule_network(src: str, tgt: str, act: str) -> str:
    if src == "on_prem":
        return (
            "Src: on-prem 10.0.0.0/16; Tgt: vpc-prod/subnet-ingest; "
            "Endpoint: Private (Cloud Interconnect / HA VPN); Region: us-central1 (default); "
            "FW: ingest-fw (tcp/443 from on-prem CIDR); "
            "DNS: <service>.googleapis.com via private DNS zone; "
            "LB/Mesh: none; Egress: VPC-SC perimeter ingest-perim"
        )
    if act in ("logs", "metrics", "event") or tgt in ("cloud_logging", "cloud_monitoring", "pubsub"):
        return (
            "Src: <service>; Tgt: managed GCP service; "
            "Endpoint: GCP-internal API; Region: us-central1 (multi-region for logs/metrics); "
            "FW: GCP-managed; DNS: <service>.googleapis.com; "
            "LB/Mesh: none; Egress: n/a"
        )
    return (
        "Src: <service>-vpc/<service>-subnet; "
        "Tgt: <target> via Private Service Connect; "
        "Endpoint: Private (Private Service Connect); "
        "Region: us-central1; FW: <service>-egress-<target> firewall rule; "
        "DNS: <target>.googleapis.com via private DNS; "
        "LB/Mesh: none; Egress: VPC-SC perimeter (default)"
    )


def _rule_performance(src: str, tgt: str, act: str) -> str:
    if act == "logs":
        return (
            "Throughput: 100 entries/sec sustained; Peak: 1000/sec burst; "
            "Latency: P50 50ms / P95 200ms / P99 1s buffer flush; "
            "Timeout: 30s; Concurrency: per-pod buffer; "
            "Rate limit: Cloud Logging API quota"
        )
    if act == "metrics":
        return (
            "Throughput: 10 points/sec sustained; Peak: 100/sec burst; "
            "Latency: P50 100ms / P95 500ms / P99 2s emit; "
            "Timeout: 30s; Concurrency: client buffer; "
            "Rate limit: 1 pt/min per stream (Cloud Monitoring)"
        )
    if act == "manages":
        return (
            "Throughput: 10 create+delete cycles/h (default); Peak: 60/h; "
            "Latency: P50 90s cluster create / P95 180s / P99 300s; "
            "Timeout: 600s per call; Concurrency: 5 parallel clusters (default); "
            "Rate limit: Dataproc quota (max clusters/region)"
        )
    if act == "validates":
        return (
            "Throughput: 1 scan per load; Peak: 60/h (default); "
            "Latency: P50 2min / P95 10min / P99 30min for ~30 rules (default baseline); "
            "Timeout: 3600s; Concurrency: 4 parallel scans; "
            "Rate limit: Dataplex scan-runs/day quota"
        )
    if act == "audit":
        return (
            "Throughput: 1 row per pipeline run; Peak: 60/h; "
            "Latency: P50 100ms / P95 500ms / P99 2s; Timeout: 30s; "
            "Concurrency: 1 per run; Rate limit: BQ Storage Write"
        )
    if tgt.startswith("bigquery") and act == "writes":
        return (
            "Throughput: 1 GB/min per cluster (default); Peak: 5 GB/min with autoscaling; "
            "Latency: P50 60s for 100 MB / P95 5min / P99 15min; "
            "Timeout: 1800s per load; Concurrency: 4 parallel writers (default); "
            "Rate limit: BQ load-jobs 1000/day + slot reservation"
        )
    if src.startswith("bigquery") and act == "reads":
        return (
            "Throughput: 2 GB/s per cluster (parallel streams); Peak: 10 GB/s with autoscaling; "
            "Latency: P50 30s for 1 GB / P95 3min / P99 10min; "
            "Timeout: 1800s per session; Concurrency: 8 read streams; "
            "Rate limit: BQ read-bytes quota"
        )
    if act == "event":
        return (
            "Throughput: 10 events/h avg (default); Peak: 60/h; "
            "Latency: P50 <1s / P95 5s / P99 10s; Timeout: managed; "
            "Concurrency: unbounded by service; Rate limit: Pub/Sub publish quota"
        )
    if act == "triggers":
        return (
            "Throughput: 10 triggers/h (default); Peak: 60/h; "
            "Latency: P50 200ms / P95 800ms / P99 2s; "
            "Timeout: 30s push deadline; Concurrency: 20 parallel DAG runs; "
            "Rate limit: Composer API quota"
        )
    if act == "poll":
        return (
            "Throughput: 12 polls/h (5-min cadence); Peak: same; "
            "Latency: P50 1s / P95 3s / P99 8s per LIST; "
            "Timeout: connect 5s / read 30s; Concurrency: 1 sensor task; "
            "Rate limit: GCS LIST quota"
        )
    if act == "uploads":
        return (
            "Throughput: 10 files/h avg (default); Peak: 60 files/h; "
            "Latency: P50 5s / P95 30s / P99 120s upload; "
            "Timeout: connect 5s / read 300s / total 600s; "
            "Concurrency: 20 parallel uploads; "
            "Rate limit: GCS default (5K req/s per bucket)"
        )
    return (
        "Throughput: 100 RPS avg (default); Peak: 500 RPS; "
        "Latency: P50 50ms / P95 200ms / P99 500ms (default); "
        "Timeout: connect 5s / read 30s / total 60s; "
        "Concurrency: 50 (default); Rate limit: service-quota default — confirm"
    )


def _rule_reliability(src: str, tgt: str, act: str) -> str:
    if act == "logs":
        return (
            "Idempotent: yes (client-assigned entry id); Retry: SDK 3x exp backoff; "
            "CB: SDK falls back to local file on persistent failure; Bulkhead: per-pod; "
            "Fallback: stderr → GKE log collection; DLQ: n/a; "
            "Delivery: at-least-once (best-effort); Replay: no"
        )
    if act == "metrics":
        return (
            "Idempotent: yes (timestamp dedup); Retry: SDK 3x exp; "
            "CB: drop on overflow (lossy by design); Bulkhead: per-stream; "
            "Fallback: log-based metrics; DLQ: n/a; "
            "Delivery: at-least-once; Replay: no (point-in-time)"
        )
    if act == "manages":
        return (
            "Idempotent: yes (cluster name = sha256(run_id)); "
            "Retry: 3x exp 30/60/120s on transient; "
            "CB: 3 consec create failures → quarantine 1h; "
            "Bulkhead: max-active-clusters=5; "
            "Fallback: smaller default cluster size on quota issue; "
            "DLQ: failed-runs audit table; Delivery: exactly-once (idempotent by name); "
            "Replay: yes (re-run Composer task)"
        )
    if act == "validates":
        return (
            "Idempotent: yes (scan-run id); Retry: 2x 300/600s; "
            "CB: per-rule (auto-skip after 5 consec fails); Bulkhead: per-scan; "
            "Fallback: continue curation with warning flag (configurable); "
            "DLQ: failed-scans audit table; "
            "Delivery: at-least-once result emit; Replay: yes (re-run scan)"
        )
    if act == "audit":
        return (
            "Idempotent: yes (PK = run_id); Retry: 5x exp (audit completeness MANDATORY); "
            "CB: n/a (always retry); Bulkhead: per-run; "
            "Fallback: dual-write to Cloud Logging on BQ unavailable; "
            "DLQ: cloud-logging fallback + reconcile job; "
            "Delivery: at-least-once; Replay: n/a (single row per run)"
        )
    if act == "event":
        return (
            "Idempotent: yes (event id dedup on subscriber); "
            "Retry: GCS-managed retry to Pub/Sub; CB: n/a; Bulkhead: per-topic; "
            "Fallback: poll-based sensor (defensive); "
            "DLQ: <topic>-dlq subscriber-side; Delivery: at-least-once; "
            "Replay: yes (Pub/Sub 7d retention)"
        )
    if act == "triggers":
        return (
            "Idempotent: yes (run_id-keyed dedup); Retry: Pub/Sub redelivery 3x then DLQ; "
            "CB: per-subscription; Bulkhead: max-attempts=5; "
            "Fallback: sensor-poll path; DLQ: gcs-arrivals-dlq → on-call review; "
            "Delivery: at-least-once; Replay: yes (Pub/Sub 7d + DAG replay)"
        )
    if act == "uploads":
        return (
            "Idempotent: yes (overwrite by deterministic object key); "
            "Retry: 3x exp 1/2/4s + jitter; CB: n/a; Bulkhead: per-source-prefix; "
            "Fallback: on-prem holding queue; DLQ: n/a (files persist locally); "
            "Delivery: at-least-once; Replay: yes (GCS object versioning)"
        )
    if act == "poll":
        return (
            "Idempotent: yes (read-only LIST); Retry: 3x linear 10/20/30s; "
            "CB: 50% fail in 60s → halt poll 5min; Bulkhead: per-DAG; "
            "Fallback: rely on event-driven path; DLQ: n/a; "
            "Delivery: at-most-once observation; Replay: n/a"
        )
    if tgt.startswith("bigquery") and act == "writes":
        return (
            "Idempotent: yes (partition + dedup on PK); Retry: 3x exp 60/120/300s; "
            "CB: per-table; Bulkhead: per-source-prefix; "
            "Fallback: GCS holding bucket, replay; DLQ: bq-write-errors table; "
            "Delivery: at-least-once (dedup downstream); "
            "Replay: yes (re-run from source)"
        )
    if src.startswith("bigquery") and act == "reads":
        return (
            "Idempotent: yes (read-only); Retry: BQ-managed stream retry; "
            "CB: per-table; Bulkhead: per-partition; "
            "Fallback: re-read from source files; DLQ: n/a; "
            "Delivery: exactly-once (session-based); "
            "Replay: yes (BQ time-travel ≤7d)"
        )
    return (
        "Idempotent: yes (default); Retry: 3x exp + jitter (default); "
        "CB: 50% error rate over 60s; Bulkhead: per-tenant 100 conn (default); "
        "Fallback: cached response (60s TTL) (default); "
        "DLQ: <service>-dlq; Delivery: at-least-once (default); "
        "Replay: yes (default — confirm)"
    )


def _rule_observability(src: str, tgt: str, act: str) -> str:
    if act == "logs":
        return (
            "Logs: meta — Cloud Logging self-monitoring; "
            "Metrics: log-entries-written + drop-rate (USE); "
            "Tracing: entries carry trace_id label; "
            "Health: Cloud Logging status; "
            "Alerts: drop-rate >0.1% / 5min → PagerDuty"
        )
    if act == "metrics":
        return (
            "Logs: meta; Metrics: meta — self-monitoring; "
            "Tracing: trace_id as label on points; "
            "Health: Cloud Monitoring status; "
            "Alerts: pipeline-error-rate >1% / 5min → PagerDuty (PRIMARY alerting surface)"
        )
    if act == "manages":
        return (
            "Logs: cluster create/delete + job status → Cloud Logging 90d; "
            "Metrics: cluster-active-count + create-latency + job-success-rate (RED); "
            "Tracing: W3C via Dataproc operator; "
            "Health: Cluster YARN ResourceManager; "
            "Alerts: create-fail 3 consec / job-fail >5% → PagerDuty"
        )
    if act == "validates":
        return (
            "Logs: rule-fail details + sample row hashes → Cloud Logging 90d; "
            "Metrics: rules-pass-rate + rows-failed (RED); "
            "Tracing: W3C; Health: Dataplex scan history; "
            "Alerts: pass-rate <95% / scan → PagerDuty DQ channel"
        )
    if act == "audit":
        return (
            "Logs: audit-write success/fail → Cloud Logging 1yr; "
            "Metrics: audit-row-count + audit-write-latency + audit-write-fail-rate; "
            "Tracing: W3C; Health: Composer DAG completion gate; "
            "Alerts: audit-write fail → PagerDuty (BLOCKING — page primary on-call)"
        )
    return (
        "Logs: structured entries (request_id, run_id, status) → Cloud Logging 30d; "
        "Metrics: RED via Cloud Monitoring; "
        "Tracing: W3C Trace Context via OTel SDK; "
        "Health: /healthz every 10s; "
        "Alerts: error rate >1% for 5min → PagerDuty primary"
    )


def _rule_compliance(src: str, tgt: str, act: str) -> str:
    base_residency = "us-central1 only (default; confirm with data-residency policy)"
    if tgt == "bigquery_audit" or act == "audit":
        return (
            f"Residency: {base_residency}; "
            f"Reg scope: SOC 2 — audit log REQUIRED for compliance; "
            f"Audit: this IS the pipeline audit log (3yr retention); "
            f"PII: none"
        )
    if tgt == "bigquery_curation":
        return (
            f"Residency: {base_residency}; "
            f"Reg scope: SOC 2 (assumed PCI/HIPAA out-of-scope; confirm with legal per-dataset); "
            f"Audit: BQ audit log 1yr (who-wrote-what); "
            f"PII: tokenization applied pre-write; row-level access policies enforced"
        )
    if src == "on_prem":
        return (
            f"Residency: {base_residency}; "
            f"Reg scope: SOC 2 + GDPR (assumed for EU-origin data — confirm with legal); "
            f"Audit: GCS Cloud Audit Logs 1yr → security archive; "
            f"PII: tagged at source schema, no PII in object names"
        )
    if act in ("logs", "metrics"):
        return (
            f"Residency: us multi-region (default — confirm if residency mandates us-only); "
            f"Reg scope: SOC 2 (logs/metrics are audit material); "
            f"Audit: 30d hot + 1yr cold export (default); "
            f"PII: stripped at emit per logging-config (assumed)"
        )
    if act == "validates":
        return (
            f"Residency: {base_residency}; "
            f"Reg scope: SOC 2 + DQ SLAs (assumed); "
            f"Audit: Dataplex Cloud Audit Logs 1yr; "
            f"PII: column-level PII tags applied as scan side-effect"
        )
    return (
        f"Residency: {base_residency}; "
        f"Reg scope: SOC 2 (default; confirm with security team); "
        f"Audit: Cloud Audit Logs 1yr → security archive (default); "
        f"PII: none in payload (assumed; tag if classification changes)"
    )


def _rule_dependencies(src: str, tgt: str, act: str, step: int | None) -> str:
    sno = f"#{step}" if step is not None else "<this connector>"
    if act == "audit":
        return (
            f"Upstream: pipeline run lifecycle connectors; "
            f"Downstream: ops reporting / SOC review (out-of-scope); "
            f"Blast: lose audit traceability (compliance impact); "
            f"Degrade: Cloud Logging until BQ recovers, reconcile via batch; "
            f"RTO: 0 (must succeed before run-complete ack); RPO: 0"
        )
    if act in ("logs", "metrics"):
        return (
            f"Upstream: any pipeline event; "
            f"Downstream: SIEM / dashboards / on-call (out-of-scope); "
            f"Blast: lose visibility (no data loss); "
            f"Degrade: local agent buffer / log-based metrics; "
            f"RTO: 5min; RPO: 5min"
        )
    if act == "manages":
        return (
            f"Upstream: trigger connectors; "
            f"Downstream: data-write connectors (Dataproc → BQ); "
            f"Blast: pipeline halt at processing; "
            f"Degrade: queue tasks in Composer scheduler; "
            f"RTO: 30min; RPO: 0 (input files persist upstream)"
        )
    if act == "validates":
        return (
            f"Upstream: staging-write connector; "
            f"Downstream: curation-write connector (gated by DQ); "
            f"Blast: curation halts until DQ passes or override; "
            f"Degrade: bypass DQ for non-critical sources with explicit flag; "
            f"RTO: 1h; RPO: 0 (staging persists)"
        )
    if act == "event":
        return (
            f"Upstream: source-write connector; "
            f"Downstream: triggered-DAG connector; "
            f"Blast: event delivery lag — sensor covers gaps; "
            f"Degrade: fall back to sensor polling; RTO: 5min; RPO: 0"
        )
    if act == "triggers":
        return (
            f"Upstream: event / sensor connector; "
            f"Downstream: cluster-management connector; "
            f"Blast: missed run — sensor catches up; "
            f"Degrade: rely on sensor polling; RTO: 5min; RPO: 0"
        )
    if act == "uploads":
        return (
            f"Upstream: on-prem source system(s); "
            f"Downstream: event-emit + sensor-poll connectors; "
            f"Blast: ingestion halts — files accumulate on-prem; "
            f"Degrade: on-prem queue, drain when GCS back; "
            f"RTO: 1h; RPO: 0 (on-prem retains until ack)"
        )
    return (
        f"Upstream: <prev connector(s)>; "
        f"Downstream: <next connector(s)>; "
        f"Blast: pipeline halt at this hop (default); "
        f"Degrade: queue upstream / fail-soft (default); "
        f"RTO: 1h (default); RPO: 0 (source data persisted)"
    )


def _rule_fill_row(src_label: str, tgt_label: str, action: str, step: int | None) -> dict[str, str]:
    """Fill all 10 detail columns deterministically for one row."""
    src = _service_type(src_label)
    tgt = _service_type(tgt_label)
    act = _action_type(action)
    return {
        "Interaction Pattern":         _rule_interaction(src, tgt, act),
        "Protocol & API":              _rule_protocol(src, tgt, act),
        "AuthN & AuthZ":               _rule_auth(src, tgt, act),
        "Data":                        _rule_data(src, tgt, act),
        "Network & Connectivity":      _rule_network(src, tgt, act),
        "Performance & SLA":           _rule_performance(src, tgt, act),
        "Reliability & Resilience":    _rule_reliability(src, tgt, act),
        "Observability":               _rule_observability(src, tgt, act),
        "Compliance & Governance":     _rule_compliance(src, tgt, act),
        "Dependencies & Failure Mode": _rule_dependencies(src, tgt, act, step),
    }


def _resolve_jira_key(diagram_name: str) -> str:
    """`PROJ-126-20260525-121616.drawio` → `PROJ-126`. Falls back to
    the bare stem if the timestamp pattern doesn't match."""
    stem = Path(diagram_name).stem
    m = re.match(r"^([A-Z]+-\d+)-\d{8}-\d{6}$", stem)
    return m.group(1) if m else stem


def _escape_cell(value: str) -> str:
    """Markdown table cells can't contain unescaped pipes or newlines."""
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _render_table(diagram, jira_key: str) -> str:
    """Build the markdown table string from a parsed Diagram."""
    # Build node-id -> label lookup once
    label_of = {n.id: n.label for n in diagram.nodes}

    # Sort edges by step_index; edges without one go last in their
    # original order (they should be rare — only fire-and-forget /
    # back-edges where the LLM explicitly passed step=0).
    with_step = sorted(
        [e for e in diagram.edges if e.step_index is not None],
        key=lambda e: e.step_index,  # type: ignore[arg-type]
    )
    without_step = [e for e in diagram.edges if e.step_index is None]
    ordered = with_step + without_step

    headers = "| " + " | ".join(name for name, _ in COLUMNS) + " |"
    sep = "|" + "|".join(["---"] * len(COLUMNS)) + "|"

    rows: list[str] = []
    for e in ordered:
        src_label = label_of.get(e.source_id, e.source_id)
        tgt_label = label_of.get(e.target_id, e.target_id)
        action = e.label or ""
        # Deterministic fill: every detail column gets a concrete GCP-
        # default value. No `{TBD}` anywhere. The LLM step (when
        # available) refines these defaults; without it, the output is
        # still complete and actionable.
        filled = _rule_fill_row(src_label, tgt_label, action, e.step_index)
        cells = {
            "Step":   str(e.step_index) if e.step_index is not None else "—",
            "Source": src_label,
            "Target": tgt_label,
            "Action": action,
        }
        cells.update(filled)
        row = "| " + " | ".join(
            _escape_cell(cells.get(name, default)) for name, default in COLUMNS
        ) + " |"
        rows.append(row)

    return "\n".join([headers, sep, *rows])


HEADER_TMPL = """# Connector Details — {jira_key}

Source diagram: `diagrams/{diagram_name}`
Source story:   `jira-stories/{story_name}`
Generated:      `{ts}` by `generate_connector_details.py` ({fill_mode})
Schema:         [docs/connector-details-template.md](../docs/connector-details-template.md)

> **Fill rule.** Every cell below carries a concrete value populated
> by the rule-based GCP-defaults engine in
> `generate_connector_details.py`. Business-decision fields use
> `(assumed)` / `(default)` markers so the table is fully
> actionable while still flagging values that need reviewer
> confirmation. The optional LLM refinement step (when an API key
> is set) tunes these defaults against the surgical story.
"""

FOOTER_TMPL = """

---
Last review:  `{{date}}` by `{{name}}`
Next review:  `{{date}}` (architecture review board)
"""


def generate(
    diagram_path: Path,
    story_path: Path | None,
    out_path: Path,
    force: bool,
    fill_mode: str,
    model: str,
) -> int:
    """Generate (and optionally LLM-fill) the connector-details table.

    fill_mode:
        - 'llm'           : require LLM auto-fill (Anthropic SDK). Fail if
                            SDK/key missing.
        - 'auto'          : try LLM; on failure, emit NEEDS_FILL delegate
                            payload (exit 2) so the calling LLM does the
                            fill. Default.
        - 'skeleton-only' : write the {TBD}-skeleton and return — no fill,
                            no delegate payload. Useful for testing.

    Returns the exit code (0 = success, 2 = delegate payload emitted).
    """
    from drawio_mcp_server.util.diagram_store import DiagramStore

    diagrams_dir = diagram_path.parent
    store = DiagramStore(diagrams_dir.resolve())
    diagram = store.load(diagram_path.name)

    if not diagram.edges:
        raise SystemExit(
            f"[gen-connectors] ERROR: {diagram_path.name} has no edges — "
            f"nothing to document."
        )

    jira_key = _resolve_jira_key(diagram_path.name)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if out_path.exists() and not force:
        # Back up the existing file so re-runs don't silently overwrite
        # human edits.
        backup = out_path.with_suffix(out_path.suffix + ".bak")
        backup.write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[gen-connectors] backed up existing → {backup.name}")

    skeleton_table = _render_table(diagram, jira_key)
    surgical_text = story_path.read_text(encoding="utf-8") if (story_path and story_path.exists()) else ""

    # --- skeleton-only (= rule-only) mode: write rule-filled and return ---
    if fill_mode == "skeleton-only":
        body = _assemble(
            jira_key, diagram_path.name,
            story_path.name if story_path else "<not supplied>",
            ts, "rule-filled (no LLM refinement)", skeleton_table,
        )
        out_path.write_text(body, encoding="utf-8")
        print(
            f"[gen-connectors] RULE-FILLED {out_path.name} "
            f"({len(diagram.edges)} rows). Every cell has a concrete "
            f"GCP-default value; no LLM refinement applied. Pass "
            f"--fill llm or --fill auto with ANTHROPIC_API_KEY set "
            f"to refine against the surgical story."
        )
        return 0

    # --- LLM fill path (default 'auto' tries this first) ---
    try:
        filled_table = _fill_table_with_anthropic(
            skeleton_table=skeleton_table,
            surgical_text=surgical_text,
            jira_key=jira_key,
            model=model,
        )
        body = _assemble(
            jira_key, diagram_path.name,
            story_path.name if story_path else "<not supplied>",
            ts, f"LLM-filled via {model}", filled_table,
        )
        out_path.write_text(body, encoding="utf-8")
        tbd_count = _count_unqualified_tbd(filled_table)
        print(
            f"[gen-connectors] AUTO-FILLED {out_path.name} via LLM "
            f"({len(diagram.edges)} rows, {tbd_count} {{TBD…}} tokens remaining)."
        )
        if tbd_count > _MAX_ANY_TBD:
            print(
                f"[gen-connectors] WARN: {tbd_count} `{{TBD…}}` tokens "
                f"found (threshold: {_MAX_ANY_TBD}). The Always-Fill "
                f"rule forbids `{{TBD}}` in any form — review the output "
                f"and replace remaining placeholders with concrete "
                f"`(assumed)` / `(default)` values. The downstream "
                f"`add_connector_table` MCP tool will refuse to embed.",
                file=sys.stderr,
            )
        return 0
    except RuntimeError as exc:
        if fill_mode == "llm":
            print(f"[gen-connectors] ERROR: {exc}", file=sys.stderr)
            return 1
        # `auto` mode: the rule-filled output is already complete and
        # contains ZERO `{TBD}` — LLM refinement was only going to
        # tune it against the surgical story. Write the rule-filled
        # file and exit 0 so downstream `add_connector_table` can
        # embed it immediately. Log the LLM unavailability for users
        # who want to set ANTHROPIC_API_KEY for refinement.
        body = _assemble(
            jira_key, diagram_path.name,
            story_path.name if story_path else "<not supplied>",
            ts, "rule-filled (LLM refinement unavailable)", skeleton_table,
        )
        out_path.write_text(body, encoding="utf-8")
        print(
            f"[gen-connectors] RULE-FILLED {out_path.name} "
            f"({len(diagram.edges)} rows). Every cell carries a "
            f"concrete GCP-default value — no {{TBD}} anywhere.",
            file=sys.stderr,
        )
        print(
            f"[gen-connectors] note: LLM refinement skipped ({exc}). "
            f"To refine the rule-defaults against the surgical story, "
            f"set ANTHROPIC_API_KEY and re-run with --fill llm or auto.",
            file=sys.stderr,
        )
        return 0


def _assemble(jira_key, diagram_name, story_name, ts, fill_mode, table) -> str:
    return (
        HEADER_TMPL.format(
            jira_key=jira_key,
            diagram_name=diagram_name,
            story_name=story_name,
            ts=ts,
            fill_mode=fill_mode,
        )
        + "\n"
        + table
        + FOOTER_TMPL
    )


# ---------------------------------------------------------------------------
# LLM fill path — Anthropic SDK
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You fill in a connector-details markdown table for a
software architecture diagram. You receive (1) the surgical Jira story
(architectural source of truth), (2) the per-column schema reference,
and (3) a skeleton markdown table with `{TBD}` placeholders. You return
ONLY the filled markdown table — no preamble, no explanation, no code
fences.

ALWAYS-FILL DIRECTIVE — **NEVER output `{TBD}` in any form**. Every cell
must carry a CONCRETE VALUE. Mark assumptions with `(assumed)` or
`(default)` rather than leaving a placeholder. Use these sources in
priority order:

1. **The surgical story** as primary source. Section 3 (In Scope) names
   components and connections — derive interaction patterns, protocols,
   data formats, sizes, validation rules from that prose. Sections 5
   (FRs) and 6 (NFRs) carry quantitative defaults (throughput, latency,
   security).

2. **GCP architectural defaults** for the named services. Examples:
   - `Cloud Storage` edge → HTTPS REST / 443 / Service Account / TLS 1.3 /
     Google-managed (or CMEK for classified).
   - `Pub/Sub` topic → Asynchronous / Event-Driven / Push / at-least-once /
     JSON or Avro / IAM-scoped subscribers.
   - `Cloud Composer` → `Dataproc` operator → gRPC over IAM-authenticated
     service-account channel; idempotent cluster create via job-name hash.
   - `BigQuery` load → BQ Load API / Service Account writer role /
     partitioned tables / 1 yr partition expiration default.
   - `Dataplex` validation → Data Quality scan API / pull-based / writes
     results back as table tags.
   - `Cloud Logging` / `Cloud Monitoring` → fire-and-forget /
     at-least-once / SDK-managed buffering.

3. **Reasonable engineering inference** for non-controversial defaults:
   idempotent + retry-with-jittered-backoff, structured logs to Cloud
   Logging, RED metrics to Cloud Monitoring, P95 latencies in the
   hundreds-of-ms range, OpenTelemetry tracing with W3C Trace Context,
   alerts on error rate >1% over 5 min → PagerDuty.

4. **For business-decision fields** (residency scope, compliance regime,
   ownership, dollar budgets, peak TPS numbers) — provide a SENSIBLE
   DEFAULT marked `(assumed)` or `(default)` so the cell renders as a
   concrete value the reviewer can confirm or override. Examples:
   - Reg scope: `SOC 2 + GDPR (assumed for EU-origin data)`
   - Residency: `us-central1 only (default; confirm with data-residency policy)`
   - PCI/HIPAA: `Out of scope (assumed; legal review for sensitive datasets)`
   - PII handling: `Column-level tagging via Dataplex (default; per-source classification applied at scan)`
   - Review cadence: `Quarterly (default architecture review cadence)`

   These cells are still actionable — the `(assumed)` label tells the
   reviewer this is a default that needs confirmation, while keeping
   the table free of placeholder syntax.

OUTPUT MUST NOT CONTAIN THE STRING `{TBD` ANYWHERE. If you find yourself
about to write `{TBD: <hint>}`, replace it with a `<hint> (assumed)`-style
concrete default instead.

Each cell must follow the **per-column sub-field shape** defined in
the schema reference. Examples:
- Interaction Pattern: `<Sync/Async>; <Pattern>; <Direction>; <Way>`
- Protocol & API: `<Protocol>; <API style>; <Port>; <Endpoint>; <Methods>; <Schema>`
- AuthN & AuthZ: `AuthN: <method>; AuthZ: <model>; Issuer: <who>; TTL: <duration>; Secret store: <where>`
- Data: `Format: <fmt>; Size: <avg>/<max>; Classification: <class>; In-transit: <crypto>; At-rest: <crypto>; Masking: <strategy>; Schema evol: <policy>`
- Network: `Src: <vpc/subnet>; Tgt: <vpc/subnet>; Endpoint: <type>; Region: <r>; FW: <rules>; DNS: <zone>; LB/Mesh: <component>; Egress: <policy>`

OUTPUT FORMAT: Return the markdown table EXACTLY in the structure
provided in the skeleton — same column count, same column order,
same row count (one row per numbered edge). Use `; ` (semicolon-space)
to separate sub-fields within a multi-field cell so the table stays
one-line-per-row. Escape any literal `|` characters in cell values
as `\\|` so they don't break the markdown table.
"""


def _fill_table_with_anthropic(
    *,
    skeleton_table: str,
    surgical_text: str,
    jira_key: str,
    model: str,
) -> str:
    """Call Claude to fill `{TBD}` cells in the skeleton table.
    Returns the filled markdown table only (no surrounding doc).
    Raises RuntimeError if the SDK is missing, the API key is unset,
    or the model returns an empty response."""
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic SDK not installed. Install with "
            "`pip install anthropic` or run with --fill skeleton-only / "
            "rely on the delegate fallback."
        ) from exc

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Export it or run with "
            "--fill skeleton-only / rely on the delegate fallback."
        )

    # Try to attach the schema reference for additional grounding.
    schema_text = ""
    if DEFAULT_TEMPLATE_DOC.exists():
        schema_text = DEFAULT_TEMPLATE_DOC.read_text(encoding="utf-8")

    user_prompt = (
        f"SURGICAL JIRA STORY (Jira key {jira_key}):\n"
        f"---\n{surgical_text or '<not supplied>'}\n---\n\n"
        f"SCHEMA REFERENCE (docs/connector-details-template.md — sub-field shapes per column):\n"
        f"---\n{schema_text or '<schema doc unavailable>'}\n---\n\n"
        f"SKELETON TABLE TO FILL (replace every `{{TBD}}` per the always-fill directive):\n"
        f"---\n{skeleton_table}\n---\n\n"
        f"Return ONLY the filled table."
    )

    client = Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}],
            }
        ],
    )

    parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    filled = "".join(parts).strip()
    if not filled:
        raise RuntimeError("Empty response from Anthropic API.")

    # Strip a leading code fence if the model added one despite the rule.
    if filled.startswith("```"):
        filled = filled.split("\n", 1)[1] if "\n" in filled else filled
        if filled.endswith("```"):
            filled = filled[: filled.rfind("```")].rstrip()
    return filled


# ---------------------------------------------------------------------------
# Delegate fallback — emit NEEDS_FILL payload for the conversational LLM
# ---------------------------------------------------------------------------


def _emit_fill_delegate_payload(
    *,
    out_path: Path,
    surgical_text: str,
    jira_key: str,
    skeleton_table: str,
    reason: str,
) -> None:
    """Print a JSON payload telling the calling LLM (e.g. Copilot Chat)
    to fill the skeleton it just wrote to `out_path`. Exits 2."""
    schema_text = ""
    if DEFAULT_TEMPLATE_DOC.exists():
        schema_text = DEFAULT_TEMPLATE_DOC.read_text(encoding="utf-8")

    payload = {
        "status": "NEEDS_FILL",
        "target_path": str(out_path),
        "jira_key": jira_key,
        "reason": reason,
        "instructions_for_calling_llm": (
            f"The connector-details skeleton has been written to "
            f"`{out_path}`. Every detail cell currently shows `{{TBD}}`. "
            f"BEFORE moving to the next step (embedding the table into "
            f"the diagram via add_connector_table), you MUST replace "
            f"EVERY `{{TBD}}` cell with a CONCRETE VALUE per the "
            f"Always-Fill directive in .github/copilot-instructions.md: "
            f"surgical story (primary) → GCP architectural defaults → "
            f"engineering inference. NEVER use `{{TBD}}` of any form in "
            f"the deliverable — for business-decision fields (residency, "
            f"compliance scope, ownership), provide a sensible default "
            f"marked `(assumed)` or `(default)`, NOT a `{{TBD}}` "
            f"placeholder. Edit the file via your Write tool. The "
            f"downstream `add_connector_table` MCP tool has a hard "
            f"pre-flight guard that REFUSES to embed if ANY `{{TBD}}` "
            f"token is found."
        ),
        "always_fill_directive_summary": (
            "ZERO {TBD} of any form in the output. Priority 1: surgical "
            "story; Priority 2: GCP defaults (Cloud Storage→HTTPS/REST/"
            "443/SA/TLS1.3, Pub/Sub→Async/Event-Driven/at-least-once/"
            "JSON or Avro); Priority 3: engineering inference "
            "(idempotent + retry-with-jittered-backoff, structured "
            "logs, RED metrics, P95 in hundreds of ms); Priority 4: "
            "for business-decision fields use sensible defaults marked "
            "'(assumed)' or '(default)' — never {TBD}."
        ),
        "schema_reference": schema_text,
        "surgical_story": surgical_text,
        "skeleton_table": skeleton_table,
    }
    print(json.dumps(payload, indent=2))
    print(
        f"\n[gen-connectors] NEEDS_FILL: skeleton written to "
        f"{out_path.name} but auto-fill failed ({reason!r}). The "
        f"calling LLM must fill it via the payload above before "
        f"add_connector_table can produce a populated diagram.",
        file=sys.stderr,
    )
    sys.exit(2)


def _count_unqualified_tbd(text: str) -> int:
    """Count `{TBD…}` occurrences of ANY form (plain `{TBD}` AND
    qualified `{TBD: <hint>}`). Both violate the always-fill rule —
    the deliverable must contain ZERO `{TBD}` tokens. Business-
    decision fields use `(assumed)`/`(default)` markers instead of
    `{TBD}` placeholders."""
    return len(re.findall(r"\{TBD", text))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Generate the per-connector documentation table for a diagram. "
            "Reads the diagram's edges, writes <KEY>-connectors.md alongside "
            "the surgical story. Cross-platform self-bootstrap."
        )
    )
    p.add_argument(
        "--diagram",
        required=True,
        help=(
            "Diagram filename under --diagrams-dir, or an absolute path. "
            "Example: PROJ-126-20260525-121616.drawio"
        ),
    )
    p.add_argument(
        "--story",
        default=None,
        help=(
            "Surgical story file (informational — recorded in the header). "
            "Example: jira-stories/PROJ-126-surgical.txt"
        ),
    )
    p.add_argument(
        "--diagrams-dir",
        type=Path,
        default=DEFAULT_DIAGRAMS_DIR,
        help=f"Diagrams root (default: {DEFAULT_DIAGRAMS_DIR}).",
    )
    p.add_argument(
        "--stories-dir",
        type=Path,
        default=DEFAULT_STORIES_DIR,
        help=f"Stories root, where the output is written (default: {DEFAULT_STORIES_DIR}).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Override the output path. Defaults to "
            "<stories-dir>/<KEY>-connectors.md."
        ),
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output without writing a .bak backup.",
    )
    p.add_argument(
        "--fill",
        choices=["auto", "llm", "skeleton-only"],
        default="auto",
        help=(
            "How to fill the {TBD} cells. "
            "'auto' (default): try Anthropic SDK; on failure emit "
            "NEEDS_FILL payload (exit 2) for the calling LLM. "
            "'llm': require Anthropic SDK; fail if unavailable. "
            "'skeleton-only': write the {TBD} skeleton, no fill."
        ),
    )
    p.add_argument(
        "--model",
        default=os.environ.get("CONNECTOR_FILL_MODEL", MODEL_DEFAULT),
        help=f"Anthropic model id for auto-fill (default: {MODEL_DEFAULT}).",
    )
    args = p.parse_args(argv)

    # Resolve diagram path
    cand = Path(args.diagram)
    if cand.is_absolute() and cand.exists():
        diagram_path = cand
    else:
        diagram_path = (args.diagrams_dir / cand.name).resolve()
    if not diagram_path.exists():
        print(f"[gen-connectors] ERROR: diagram not found: {diagram_path}", file=sys.stderr)
        return 1

    # Resolve story path (informational)
    story_path: Path | None = None
    if args.story:
        sp = Path(args.story)
        if not sp.is_absolute():
            sp = (REPO_ROOT / sp).resolve() if "/" in args.story else (args.stories_dir / sp.name).resolve()
        if sp.exists():
            story_path = sp
        else:
            print(
                f"[gen-connectors] WARN: --story file not found at {sp}; "
                f"header will note it's missing.",
                file=sys.stderr,
            )

    jira_key = _resolve_jira_key(diagram_path.name)
    out_path = args.output.resolve() if args.output else (args.stories_dir.resolve() / f"{jira_key}-connectors.md")

    try:
        rc = generate(
            diagram_path,
            story_path,
            out_path,
            force=args.force,
            fill_mode=args.fill,
            model=args.model,
        )
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        print(f"[gen-connectors] ERROR: {exc}", file=sys.stderr)
        return 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
