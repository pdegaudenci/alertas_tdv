"""
Servicio de escritura en AWS S3.

Responsabilidad:
- Crear cliente S3 con boto3.
- Subir contenido JSONL al bucket configurado.
- No contiene lógica de trading.
"""

from typing import Optional
import boto3

from app.core.config import (
    AWS_REGION,
    S3_BUCKET_NAME,
)
from app.core.logging import log_event


_s3_client = None


def get_s3_client():
    global _s3_client

    if _s3_client is not None:
        return _s3_client

    _s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION or None,
    )

    log_event("s3_client_init_ok", {
        "bucket_configured": bool(S3_BUCKET_NAME),
        "region": AWS_REGION,
    })

    return _s3_client


def upload_text_to_s3(
    object_name: str,
    content: str,
    content_type: str = "application/x-ndjson",
) -> dict:
    if not S3_BUCKET_NAME:
        return {
            "ok": False,
            "uploaded": False,
            "error": "S3_BUCKET_NAME is not configured",
        }

    try:
        client = get_s3_client()

        client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=object_name,
            Body=content.encode("utf-8"),
            ContentType=content_type,
        )

        s3_uri = f"s3://{S3_BUCKET_NAME}/{object_name}"

        log_event("s3_upload_ok", {
            "s3_uri": s3_uri,
            "content_type": content_type,
        })

        return {
            "ok": True,
            "uploaded": True,
            "s3_uri": s3_uri,
        }

    except Exception as e:
        log_event("s3_upload_error", {
            "object_name": object_name,
            "error": str(e),
        })

        return {
            "ok": False,
            "uploaded": False,
            "error": str(e),
        }