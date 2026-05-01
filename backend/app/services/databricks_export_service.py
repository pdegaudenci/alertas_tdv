"""
Servicio de exportación para Databricks / Lakehouse.

FASE 1:
- No cambia el comportamiento actual del backend.
- No sustituye Supabase.
- No afecta la validación.
- Solo prepara un contrato lógico para exportar eventos a una capa Data Lake.

IMPORTANTE:
En Vercel, /tmp es efímero. Esto sirve como primer paso de arquitectura.
En FASE 2 se reemplazará por GCS, S3, Azure Blob o el storage elegido.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

try:
    import google.auth
except Exception:
    google = None

from app.utils.json_utils import sanitize_for_json
from app.core.logging import log_event


ENABLE_DATABRICKS_EXPORT = (
    os.getenv("ENABLE_DATABRICKS_EXPORT", "false").lower() == "true"
)

DATABRICKS_EXPORT_BASE_PATH = os.getenv(
    "DATABRICKS_EXPORT_BASE_PATH",
    "/tmp/trading_lakehouse"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_current_gcp_identity() -> Dict[str, Any]:
    """
    Obtiene la identidad que está ejecutando el código.

    Funciona en:
    - Cloud Composer
    - GCE
    - Cloud Run
    - GCP runtime con metadata server

    En local puede devolver service_account_email=None si usas usuario ADC.
    """

    identity = {
        "project_id": None,
        "service_account_email": None,
        "source": None,
    }

    try:
        if google is not None:
            credentials, project_id = google.auth.default()
            identity["project_id"] = project_id
            identity["service_account_email"] = getattr(
                credentials,
                "service_account_email",
                None,
            )
            identity["source"] = "google.auth.default"
    except Exception as e:
        identity["google_auth_error"] = str(e)

    if not identity.get("service_account_email"):
        try:
            url = (
                "http://metadata.google.internal/computeMetadata/v1/"
                "instance/service-accounts/default/email"
            )
            headers = {"Metadata-Flavor": "Google"}

            response = requests.get(
                url,
                headers=headers,
                timeout=2,
            )

            if response.ok:
                identity["service_account_email"] = response.text
                identity["source"] = "gcp_metadata_server"

        except Exception as e:
            identity["metadata_error"] = str(e)

    print("CURRENT_GCP_IDENTITY:", json.dumps(identity, indent=2, default=str))

    return identity


# Print automático al cargar el módulo
CURRENT_GCP_IDENTITY = get_current_gcp_identity()


def _safe_partition_value(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default

    value_str = str(value).strip()

    if not value_str:
        return default

    return (
        value_str
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace(":", "_")
        .lower()
    )


def _extract_signal(payload: Dict[str, Any]) -> Dict[str, Any]:
    signal = payload.get("signal")
    return signal if isinstance(signal, dict) else {}


def _build_export_partition_path(payload: Dict[str, Any]) -> str:
    now = _utc_now()

    signal = _extract_signal(payload)

    symbol = (
        signal.get("symbol")
        or payload.get("symbol")
        or payload.get("ticker")
        or "unknown"
    )

    timeframe = (
        signal.get("tf")
        or payload.get("tf")
        or payload.get("timeframe")
        or "unknown"
    )

    message_type = payload.get("message_type") or "unknown"

    processing_date = now.strftime("%Y-%m-%d")

    return os.path.join(
        DATABRICKS_EXPORT_BASE_PATH,
        "bronze",
        "trading_alerts",
        f"processing_date={processing_date}",
        f"symbol={_safe_partition_value(symbol)}",
        f"tf={_safe_partition_value(timeframe)}",
        f"message_type={_safe_partition_value(message_type)}",
    )


def build_databricks_bronze_event(
    payload: Dict[str, Any],
    validation: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Construye un evento Bronze listo para Data Lake.

    Mantiene el payload completo en raw_payload para no perder información.
    """

    now = _utc_now()
    signal = _extract_signal(payload)

    return sanitize_for_json({
        "event_uid": payload.get("event_uid"),
        "schema_version": payload.get("schema_version"),
        "message_type": payload.get("message_type"),
        "trace_id": trace_id,

        "symbol": (
            signal.get("symbol")
            or payload.get("symbol")
            or payload.get("ticker")
        ),
        "tf": (
            signal.get("tf")
            or payload.get("tf")
            or payload.get("timeframe")
        ),
        "event": (
            signal.get("event")
            or payload.get("event")
        ),
        "side": (
            signal.get("side")
            or payload.get("side")
        ),
        "price": (
            signal.get("price")
            or signal.get("close")
            or payload.get("price")
        ),

        "validation_approve": (
            validation.get("validation", {}).get("approve")
            if isinstance(validation, dict)
            and isinstance(validation.get("validation"), dict)
            else None
        ),
        "validation_confidence": (
            validation.get("validation", {}).get("confidence")
            if isinstance(validation, dict)
            and isinstance(validation.get("validation"), dict)
            else None
        ),
        "probability_tp_before_sl": (
            validation.get("validation", {}).get("probability_tp_before_sl")
            if isinstance(validation, dict)
            and isinstance(validation.get("validation"), dict)
            else None
        ),

        "raw_payload": payload,
        "raw_validation": validation or {},

        "ingestion_ts": now.isoformat(),
        "processing_date": now.strftime("%Y-%m-%d"),
        "source": "fastapi_trading_backend",
        "lakehouse_layer": "bronze",
    })


def export_event_for_databricks(
    payload: Dict[str, Any],
    validation: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Exporta un evento para Databricks.

    FASE 1:
    - Si ENABLE_DATABRICKS_EXPORT=false, no hace nada.
    - Si ENABLE_DATABRICKS_EXPORT=true, escribe JSONL en /tmp o ruta configurada.
    """

    if not ENABLE_DATABRICKS_EXPORT:
        return {
            "ok": True,
            "exported": False,
            "reason": "ENABLE_DATABRICKS_EXPORT=false",
        }

    try:
        bronze_event = build_databricks_bronze_event(
            payload=payload,
            validation=validation,
            trace_id=trace_id,
        )

        partition_path = _build_export_partition_path(payload)
        os.makedirs(partition_path, exist_ok=True)

        now = _utc_now()
        event_uid = _safe_partition_value(payload.get("event_uid"), "no_event_uid")
        filename = f"event_{event_uid}_{now.strftime('%Y%m%dT%H%M%S%f')}.jsonl"
        file_path = os.path.join(partition_path, filename)

        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(bronze_event, ensure_ascii=False, default=str))
            fh.write("\n")

        log_event("databricks_export_success", {
            "trace_id": trace_id,
            "file_path": file_path,
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
        })

        return {
            "ok": True,
            "exported": True,
            "file_path": file_path,
            "layer": "bronze",
        }

    except Exception as e:
        log_event("databricks_export_error", {
            "trace_id": trace_id,
            "error": str(e),
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
        })

        return {
            "ok": False,
            "exported": False,
            "error": str(e),
        }