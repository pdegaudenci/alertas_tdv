"""
Servicio de escritura en Google Cloud Storage.

Responsabilidad:
- Crear cliente GCS desde:
  1. GCP_SERVICE_ACCOUNT_JSON_BASE64, recomendado para Vercel.
  2. GOOGLE_APPLICATION_CREDENTIALS, recomendado para local.
  3. Application Default Credentials, si aplica.
- Subir contenido JSONL al bucket configurado.

No contiene lógica de trading.
"""

import base64
import json
from typing import Optional

from google.cloud import storage
from google.oauth2 import service_account

from app.core.config import (
    GCP_SERVICE_ACCOUNT_JSON_BASE64,
    GCS_BUCKET_NAME,
)
from app.core.logging import log_event


_gcs_client: Optional[storage.Client] = None


def get_gcs_client() -> storage.Client:
    global _gcs_client

    if _gcs_client is not None:
        return _gcs_client

    if GCP_SERVICE_ACCOUNT_JSON_BASE64:
        decoded = base64.b64decode(GCP_SERVICE_ACCOUNT_JSON_BASE64).decode("utf-8")
        info = json.loads(decoded)

        credentials = service_account.Credentials.from_service_account_info(info)
        _gcs_client = storage.Client(
            project=info.get("project_id"),
            credentials=credentials,
        )

        log_event("gcs_client_init_base64_ok", {
            "project_id": info.get("project_id"),
            "bucket_configured": bool(GCS_BUCKET_NAME),
        })

        return _gcs_client

    _gcs_client = storage.Client()

    log_event("gcs_client_init_default_ok", {
        "bucket_configured": bool(GCS_BUCKET_NAME),
    })

    return _gcs_client


def upload_text_to_gcs(
    object_name: str,
    content: str,
    content_type: str = "application/json",
) -> dict:
    if not GCS_BUCKET_NAME:
        return {
            "ok": False,
            "uploaded": False,
            "error": "GCS_BUCKET_NAME is not configured",
        }

    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(object_name)

        blob.upload_from_string(
            content,
            content_type=content_type,
        )

        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{object_name}"

        log_event("gcs_upload_ok", {
            "gcs_uri": gcs_uri,
            "content_type": content_type,
        })

        return {
            "ok": True,
            "uploaded": True,
            "gcs_uri": gcs_uri,
        }

    except Exception as e:
        log_event("gcs_upload_error", {
            "object_name": object_name,
            "error": str(e),
        })

        return {
            "ok": False,
            "uploaded": False,
            "error": str(e),
        }