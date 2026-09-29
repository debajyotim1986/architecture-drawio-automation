"""
app/looker_folders.py — Step 5.4: list the dashboards published in a tenant's Looker folder.

Called by the Partner Details API after the Tenant Registry lookup (5.3) has returned
`looker_folder_id` for the tenant. Talks to Looker API 4.0 through the Reverse Proxy's
internal API door (Spoke 1 -> 5a DNS -> 5b HUB transit -> Spoke 2 Looker :19999).

Two equivalent implementations are shown:
  A. Looker Python SDK   (recommended: handles login + token refresh for you)
  B. Plain HTTP calls    (same two requests, spelled out)

Environment (set in the Deployment, no secrets here):
  GCP_PROJECT            lbg-partner-analytics-prod
  LOOKER_API_URL         https://looker-api.rp.internal      # SDK appends /api/4.0 itself
  REQUESTS_CA_BUNDLE     /etc/ssl/internal-ca.pem            # trusts the Reverse Proxy's internal cert
Secret Manager (read via Workload Identity, never in YAML):
  looker-api-client-id / looker-api-client-secret            # API3 key of a Looker service user
"""
import os
import threading
import time
from functools import lru_cache

import requests
from cachetools import TTLCache
from fastapi import HTTPException
from google.cloud import secretmanager

GCP_PROJECT = os.environ["GCP_PROJECT"]
LOOKER_API_URL = os.environ["LOOKER_API_URL"].rstrip("/")
DASHBOARD_CACHE_TTL = int(os.environ.get("DASHBOARD_CACHE_TTL", "300"))   # 5 min per tenant
HTTP_TIMEOUT = (3, 10)                                                     # connect, read seconds

_sm = secretmanager.SecretManagerServiceClient()
_cache: TTLCache = TTLCache(maxsize=1000, ttl=DASHBOARD_CACHE_TTL)
_lock = threading.Lock()


@lru_cache(maxsize=None)
def _secret(name: str) -> str:
    """Read once per pod; the pod's Workload Identity grants secretAccessor on these two secrets only."""
    path = f"projects/{GCP_PROJECT}/secrets/{name}/versions/latest"
    return _sm.access_secret_version(name=path).payload.data.decode()


# =============================================================================================
# A. Looker Python SDK (looker-sdk==24.*)
# =============================================================================================
import looker_sdk
from looker_sdk import error as looker_error

_sdk = None


def _get_sdk():
    """Create the SDK once. It calls POST /api/4.0/login itself and refreshes the token on expiry."""
    global _sdk
    if _sdk is None:
        os.environ["LOOKERSDK_BASE_URL"] = LOOKER_API_URL
        os.environ["LOOKERSDK_API_VERSION"] = "4.0"
        os.environ["LOOKERSDK_VERIFY_SSL"] = "true"
        os.environ["LOOKERSDK_TIMEOUT"] = "10"
        os.environ["LOOKERSDK_CLIENT_ID"] = _secret("looker-api-client-id")
        os.environ["LOOKERSDK_CLIENT_SECRET"] = _secret("looker-api-client-secret")
        _sdk = looker_sdk.init40()
    return _sdk


def tenant_dashboards(tenant_id: str, folder_id: str) -> list[dict]:
    """[{id, title}] published in Partners/<tenant>. Cached per tenant; fail closed on problems."""
    with _lock:
        if tenant_id in _cache:
            return _cache[tenant_id]

    try:
        dashes = _get_sdk().folder_dashboards(folder_id=folder_id, fields="id,title,deleted")
    except looker_error.SDKError as exc:
        # 404 = folder id in the registry no longer exists in Looker -> treat as "no content"
        if "404" in str(exc):
            raise HTTPException(403, "tenant folder not found in Looker") from exc
        raise HTTPException(503, "Looker unavailable") from exc

    result = [{"id": str(d.id), "title": d.title or ""} for d in dashes if not d.deleted]
    if not result:
        raise HTTPException(403, "no dashboards published for this tenant")

    with _lock:
        _cache[tenant_id] = result
    return result


# =============================================================================================
# B. The same thing as plain HTTP (what the SDK does under the hood)
# =============================================================================================
_token = {"value": None, "expires_at": 0.0}


def _access_token() -> str:
    """POST /api/4.0/login with the API3 client id/secret -> short-lived access token (cached)."""
    with _lock:
        if _token["value"] and time.time() < _token["expires_at"] - 60:
            return _token["value"]
    r = requests.post(
        f"{LOOKER_API_URL}/api/4.0/login",
        data={"client_id": _secret("looker-api-client-id"),
              "client_secret": _secret("looker-api-client-secret")},
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()                      # 401 here = wrong or rotated credentials
    body = r.json()                           # {"access_token": "...", "token_type": "Bearer", "expires_in": 3600}
    with _lock:
        _token["value"] = body["access_token"]
        _token["expires_at"] = time.time() + int(body["expires_in"])
    return _token["value"]


def tenant_dashboards_http(tenant_id: str, folder_id: str) -> list[dict]:
    """GET /api/4.0/folders/{folder_id}/dashboards?fields=id,title,deleted"""
    with _lock:
        if tenant_id in _cache:
            return _cache[tenant_id]
    try:
        r = requests.get(
            f"{LOOKER_API_URL}/api/4.0/folders/{folder_id}/dashboards",
            params={"fields": "id,title,deleted"},
            headers={"Authorization": f"token {_access_token()}"},
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise HTTPException(503, "Looker unavailable") from exc

    if r.status_code == 404:
        raise HTTPException(403, "tenant folder not found in Looker")
    if r.status_code == 401:                  # token expired early or revoked: drop it, caller may retry
        _token["value"] = None
        raise HTTPException(503, "Looker authentication failed")
    r.raise_for_status()

    result = [{"id": str(d["id"]), "title": d.get("title") or ""} for d in r.json() if not d.get("deleted")]
    if not result:
        raise HTTPException(403, "no dashboards published for this tenant")
    with _lock:
        _cache[tenant_id] = result
    return result


# =============================================================================================
# How the Partner Details API uses it (5.2 -> 5.3 -> 5.4 -> 5.5)
# =============================================================================================
# @app.get("/internal/partners/{partner_id}/details")
# def partner_details(partner_id: str, request: Request):
#     caller = verify_jwt(request)                                   # 5.1 already done by Looker API; repeat here
#     rec = registry.require_active(partner_id)                      # 5.3 Cloud SQL
#     dashboards = tenant_dashboards(rec.tenant_id, rec.looker_folder_id)   # 5.4 Looker API
#     home = next((d["id"] for d in dashboards if d["title"].lower() == "home"), dashboards[0]["id"])
#     return {                                                       # 5.5 returned to Looker API
#         "partner_id": rec.partner_id, "tenant_id": rec.tenant_id,
#         "status": rec.partner_status, "max_role": rec.max_role,
#         "looker": {"group_id": rec.looker_group_id, "folder_id": rec.looker_folder_id},
#         "dashboards": dashboards, "home_dashboard_id": home,
#     }
