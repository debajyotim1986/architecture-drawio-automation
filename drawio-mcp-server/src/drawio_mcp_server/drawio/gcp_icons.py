"""GCP service name -> SVG path + draw.io image style builder.

The draw.io VS Code extension cannot render relative file paths or
`;base64,` data URIs (the style parser splits on `;`). The only reliable
embed is a URL-encoded `data:image/svg+xml,` URI, which we build here so
the LLM does not have to do encoding gymnastics.

Lookup is case/space/underscore-insensitive. Unknown names fall back to a
heuristic `<snake>/<snake>.svg` lookup so newly added icons work without a
code change.
"""

from __future__ import annotations

import urllib.parse
from pathlib import Path

# Curated map. Keys are normalised (lowercased, non-alnum stripped) friendly
# names. Values are paths relative to the icons root. The snake_case service
# set is preferred over the capitalised category folders because it has 1:1
# service icons.
GCP_ICON_PATHS: dict[str, str] = {
    # Compute / serverless
    "cloudrun": "cloud_run/cloud_run.svg",
    "cloudfunctions": "cloud_functions/cloud_functions.svg",
    "functions": "cloud_functions/cloud_functions.svg",
    "appengine": "app_engine/app_engine.svg",
    "computeengine": "compute_engine/compute_engine.svg",
    "gce": "compute_engine/compute_engine.svg",
    "gke": "google_kubernetes_engine/google_kubernetes_engine.svg",
    "googlekubernetesengine": "google_kubernetes_engine/google_kubernetes_engine.svg",
    "kubernetesengine": "google_kubernetes_engine/google_kubernetes_engine.svg",
    "kuberun": "kuberun/kuberun.svg",
    "batch": "batch/batch.svg",
    "anthos": "anthos/anthos.svg",
    "cloudtpu": "cloud_tpu/cloud_tpu.svg",
    "tpu": "cloud_tpu/cloud_tpu.svg",
    # Databases
    "bigquery": "bigquery/bigquery.svg",
    "cloudsql": "cloud_sql/cloud_sql.svg",
    "sql": "cloud_sql/cloud_sql.svg",
    "cloudspanner": "cloud_spanner/cloud_spanner.svg",
    "spanner": "cloud_spanner/cloud_spanner.svg",
    "bigtable": "bigtable/bigtable.svg",
    "firestore": "firestore/firestore.svg",
    "datastore": "datastore/datastore.svg",
    "memorystore": "memorystore/memorystore.svg",
    # Storage
    "cloudstorage": "cloud_storage/cloud_storage.svg",
    "gcs": "cloud_storage/cloud_storage.svg",
    "filestore": "filestore/filestore.svg",
    "persistentdisk": "persistent_disk/persistent_disk.svg",
    # Messaging / data
    "pubsub": "pubsub/pubsub.svg",
    "cloudpubsub": "pubsub/pubsub.svg",
    "dataflow": "dataflow/dataflow.svg",
    "dataproc": "dataproc/dataproc.svg",
    "datafusion": "cloud_data_fusion/cloud_data_fusion.svg",
    "clouddatafusion": "cloud_data_fusion/cloud_data_fusion.svg",
    "composer": "cloud_composer/cloud_composer.svg",
    "cloudcomposer": "cloud_composer/cloud_composer.svg",
    "eventarc": "eventarc/eventarc.svg",
    "workflows": "workflows/workflows.svg",
    "cloudtasks": "cloud_tasks/cloud_tasks.svg",
    "cloudscheduler": "cloud_scheduler/cloud_scheduler.svg",
    "datastream": "datastream/datastream.svg",
    # AI / ML
    "vertexai": "vertexai/vertexai.svg",
    "dialogflow": "dialogflow/dialogflow.svg",
    "documentai": "document_ai/document_ai.svg",
    "automl": "automl/automl.svg",
    # Networking / security
    "apigee": "apigee_api_platform/apigee_api_platform.svg",
    "cloudloadbalancing": "cloud_load_balancing/cloud_load_balancing.svg",
    "loadbalancer": "cloud_load_balancing/cloud_load_balancing.svg",
    "loadbalancing": "cloud_load_balancing/cloud_load_balancing.svg",
    "cloudcdn": "cloud_cdn/cloud_cdn.svg",
    "cdn": "cloud_cdn/cloud_cdn.svg",
    "cloudarmor": "cloud_armor/cloud_armor.svg",
    "cloudnat": "cloud_nat/cloud_nat.svg",
    "clouddns": "cloud_dns/cloud_dns.svg",
    "cloudvpn": "cloud_vpn/cloud_vpn.svg",
    "vpc": "virtual_private_cloud/virtual_private_cloud.svg",
    "virtualprivatecloud": "virtual_private_cloud/virtual_private_cloud.svg",
    "iam": "identity_and_access_management/identity_and_access_management.svg",
    "identityandaccessmanagement": "identity_and_access_management/identity_and_access_management.svg",
    "identityplatform": "identity_platform/identity_platform.svg",
    "secretmanager": "secret_manager/secret_manager.svg",
    "kms": "key_management_service/key_management_service.svg",
    "keymanagementservice": "key_management_service/key_management_service.svg",
    "cloudapigateway": "cloud_api_gateway/cloud_api_gateway.svg",
    "apigateway": "cloud_api_gateway/cloud_api_gateway.svg",
    # Observability
    "cloudlogging": "cloud_logging/cloud_logging.svg",
    "logging": "cloud_logging/cloud_logging.svg",
    "cloudmonitoring": "cloud_monitoring/cloud_monitoring.svg",
    "monitoring": "cloud_monitoring/cloud_monitoring.svg",
    "cloudtrace": "trace/trace.svg",
    "trace": "trace/trace.svg",
    "errorreporting": "error_reporting/error_reporting.svg",
    # DevOps
    "cloudbuild": "cloud_build/cloud_build.svg",
    "clouddeploy": "cloud_deploy/cloud_deploy.svg",
    "artifactregistry": "artifact_registry/artifact_registry.svg",
    "containerregistry": "container_registry/container_registry.svg",
    # Generic fallback
    "googlecloud": "cloud_generic/cloud_generic.svg",
    "gcp": "cloud_generic/cloud_generic.svg",
    "cloudgeneric": "cloud_generic/cloud_generic.svg",
}


def _canonical(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _snake(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")


def resolve_icon(name: str, icons_root: Path) -> Path | None:
    """Resolve a friendly GCP service name to an SVG file under `icons_root`.

    Returns ``None`` if no match. Tries the curated registry first, then a
    `<snake>/<snake>.svg` heuristic so the registry doesn't need to list
    every icon in the set.
    """
    if not icons_root.is_dir():
        return None

    rel = GCP_ICON_PATHS.get(_canonical(name))
    if rel:
        path = icons_root / rel
        if path.is_file():
            return path

    snake = _snake(name)
    if snake:
        fallback = icons_root / snake / f"{snake}.svg"
        if fallback.is_file():
            return fallback

    return None


def build_gcp_image_style(svg_path: Path) -> str:
    """Build the draw.io `shape=image;...` style with an inline URL-encoded SVG."""
    svg_text = svg_path.read_text(encoding="utf-8")
    encoded = urllib.parse.quote(svg_text, safe="")
    return (
        "shape=image;html=1;labelBackgroundColor=#ffffff;"
        "verticalLabelPosition=bottom;verticalAlign=top;"
        f"image=data:image/svg+xml,{encoded}"
    )


def known_icons() -> list[str]:
    """Sorted canonical service names (for tool descriptions / diagnostics)."""
    return sorted(GCP_ICON_PATHS.keys())


# Patterns matched against a node label to detect GCP services automatically.
# Longest patterns first so "Cloud SQL" beats "Cloud" and "Cloud Functions"
# beats "Cloud". All matching is case-insensitive. The value is the canonical
# key into GCP_ICON_PATHS.
_LABEL_PATTERNS: list[tuple[str, str]] = [
    ("google kubernetes engine", "gke"),
    ("kubernetes engine", "gke"),
    ("cloud load balancing", "cloudloadbalancing"),
    ("cloud load balancer", "cloudloadbalancing"),
    ("load balancer", "loadbalancer"),
    ("cloud functions", "cloudfunctions"),
    ("cloud function", "cloudfunctions"),
    ("cloud storage", "cloudstorage"),
    ("cloud spanner", "cloudspanner"),
    ("cloud composer", "cloudcomposer"),
    ("cloud scheduler", "cloudscheduler"),
    ("cloud tasks", "cloudtasks"),
    ("cloud build", "cloudbuild"),
    ("cloud deploy", "clouddeploy"),
    ("cloud armor", "cloudarmor"),
    ("cloud cdn", "cloudcdn"),
    ("cloud dns", "clouddns"),
    ("cloud vpn", "cloudvpn"),
    ("cloud nat", "cloudnat"),
    ("cloud logging", "cloudlogging"),
    ("cloud monitoring", "cloudmonitoring"),
    ("cloud trace", "cloudtrace"),
    ("cloud sql", "cloudsql"),
    ("cloud run", "cloudrun"),
    ("compute engine", "computeengine"),
    ("app engine", "appengine"),
    ("vertex ai", "vertexai"),
    ("document ai", "documentai"),
    ("data fusion", "datafusion"),
    ("secret manager", "secretmanager"),
    ("artifact registry", "artifactregistry"),
    ("container registry", "containerregistry"),
    ("identity platform", "identityplatform"),
    ("identity and access management", "iam"),
    ("api gateway", "apigateway"),
    ("error reporting", "errorreporting"),
    ("bigquery", "bigquery"),
    ("big query", "bigquery"),
    ("bigtable", "bigtable"),
    ("firestore", "firestore"),
    ("datastore", "datastore"),
    ("dataflow", "dataflow"),
    ("dataproc", "dataproc"),
    ("datastream", "datastream"),
    ("pub/sub", "pubsub"),
    ("pubsub", "pubsub"),
    ("pub sub", "pubsub"),
    ("memorystore", "memorystore"),
    ("apigee", "apigee"),
    ("dialogflow", "dialogflow"),
    ("automl", "automl"),
    ("workflows", "workflows"),
    ("eventarc", "eventarc"),
    ("anthos", "anthos"),
    ("kuberun", "kuberun"),
    ("filestore", "filestore"),
    ("alloydb", "alloydb"),
    ("gke", "gke"),
    ("iam", "iam"),
    ("kms", "kms"),
    ("vpc", "vpc"),
    ("gcs", "gcs"),
    ("tpu", "tpu"),
]


def detect_icon_from_label(label: str) -> str | None:
    """Return the canonical icon key when `label` clearly names a GCP service.

    Designed to be conservative: matches on word boundaries against a curated
    list of service names so "BigQuery audited tables" or "Dashboard (Cloud
    Run)" trigger the icon, but a random label that happens to contain "cloud"
    does not. Returns None when nothing matches.
    """
    if not label:
        return None
    haystack = f" {label.lower()} "
    # Replace common punctuation with spaces so "(Cloud Run)" matches.
    for ch in "()[]{}<>/\\,;:|":
        haystack = haystack.replace(ch, " ")
    for needle, key in _LABEL_PATTERNS:
        if f" {needle} " in haystack:
            return key
    return None
