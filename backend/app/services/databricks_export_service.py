"""
Servicio de exportación para Databricks / Lakehouse.

FASE 2:
- Soporta export local para pruebas.
- Soporta export a Google Cloud Storage.
- Mantiene contrato Bronze.
- No sustituye Supabase.
- No afecta validación, Telegram ni dashboard operativo.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.utils.json_utils import sanitize_for_json
from app.core.logging import log_event
from app.core.config import (
    ENABLE_DATABRICKS_EXPORT,
    DATABRICKS_EXPORT_TARGET,
    DATABRICKS_EXPORT_BASE_PATH,
    GCS_BASE_PREFIX,
)
from app.services.gcs_storage_service import upload_text_to_gcs


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _extract_partition_values(payload: Dict[str, Any]) -> dict:
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

    return {
        "processing_date": now.strftime("%Y-%m-%d"),
        "symbol": _safe_partition_value(symbol),
        "tf": _safe_partition_value(timeframe),
        "message_type": _safe_partition_value(message_type),
    }


def _build_relative_object_path(payload: Dict[str, Any]) -> str:
    now = _utc_now()
    p = _extract_partition_values(payload)

    event_uid = _safe_partition_value(payload.get("event_uid"), "no_event_uid")
    filename = f"event_{event_uid}_{now.strftime('%Y%m%dT%H%M%S%f')}.jsonl"

    return "/".join([
        GCS_BASE_PREFIX.strip("/"),
        f"processing_date={p['processing_date']}",
        f"symbol={p['symbol']}",
        f"tf={p['tf']}",
        f"message_type={p['message_type']}",
        filename,
    ])


def _build_local_partition_path(payload: Dict[str, Any]) -> str:
    p = _extract_partition_values(payload)

    return os.path.join(
        DATABRICKS_EXPORT_BASE_PATH,
        "bronze",
        "trading_alerts",
        f"processing_date={p['processing_date']}",
        f"symbol={p['symbol']}",
        f"tf={p['tf']}",
        f"message_type={p['message_type']}",
    )


def build_databricks_bronze_event(
    payload: Dict[str, Any],
    validation: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    now = _utc_now()
    signal = _extract_signal(payload)

    validation_block = (
        validation.get("validation", {})
        if isinstance(validation, dict) and isinstance(validation.get("validation"), dict)
        else {}
    )

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

        "validation_approve": validation_block.get("approve"),
        "validation_confidence": validation_block.get("confidence"),
        "probability_tp_before_sl": validation_block.get("probability_tp_before_sl"),

        "raw_payload": payload,
        "raw_validation": validation or {},

        "ingestion_ts": now.isoformat(),
        "processing_date": now.strftime("%Y-%m-%d"),
        "source": "fastapi_trading_backend",
        "lakehouse_layer": "bronze",
    })


def _export_local(
    payload: Dict[str, Any],
    bronze_event: Dict[str, Any],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    partition_path = _build_local_partition_path(payload)
    os.makedirs(partition_path, exist_ok=True)

    now = _utc_now()
    event_uid = _safe_partition_value(payload.get("event_uid"), "no_event_uid")
    filename = f"event_{event_uid}_{now.strftime('%Y%m%dT%H%M%S%f')}.jsonl"
    file_path = os.path.join(partition_path, filename)

    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(bronze_event, ensure_ascii=False, default=str))
        fh.write("\n")

    log_event("databricks_export_local_success", {
        "trace_id": trace_id,
        "file_path": file_path,
        "event_uid": payload.get("event_uid"),
        "message_type": payload.get("message_type"),
    })

    return {
        "ok": True,
        "exported": True,
        "target": "local",
        "file_path": file_path,
        "layer": "bronze",
    }


def _export_gcs(
    payload: Dict[str, Any],
    bronze_event: Dict[str, Any],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    object_name = _build_relative_object_path(payload)

    content = json.dumps(bronze_event, ensure_ascii=False, default=str) + "\n"

    upload_result = upload_text_to_gcs(
        object_name=object_name,
        content=content,
        content_type="application/x-ndjson",
    )

    if upload_result.get("ok"):
        log_event("databricks_export_gcs_success", {
            "trace_id": trace_id,
            "gcs_uri": upload_result.get("gcs_uri"),
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
        })

        return {
            "ok": True,
            "exported": True,
            "target": "gcs",
            "gcs_uri": upload_result.get("gcs_uri"),
            "layer": "bronze",
        }

    log_event("databricks_export_gcs_error", {
        "trace_id": trace_id,
        "error": upload_result.get("error"),
        "event_uid": payload.get("event_uid"),
        "message_type": payload.get("message_type"),
    })

    return {
        "ok": False,
        "exported": False,
        "target": "gcs",
        "error": upload_result.get("error"),
    }


def export_event_for_databricks(
    payload: Dict[str, Any],
    validation: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
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

        if DATABRICKS_EXPORT_TARGET == "gcs":
            return _export_gcs(
                payload=payload,
                bronze_event=bronze_event,
                trace_id=trace_id,
            )

        if DATABRICKS_EXPORT_TARGET == "local":
            return _export_local(
                payload=payload,
                bronze_event=bronze_event,
                trace_id=trace_id,
            )

        return {
            "ok": False,
            "exported": False,
            "error": f"Unsupported DATABRICKS_EXPORT_TARGET={DATABRICKS_EXPORT_TARGET}",
        }

    except Exception as e:
        log_event("databricks_export_error", {
            "trace_id": trace_id,
            "error": str(e),
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
            "target": DATABRICKS_EXPORT_TARGET,
        })

        return {
            "ok": False,
            "exported": False,
            "target": DATABRICKS_EXPORT_TARGET,
            "error": str(e),
        }