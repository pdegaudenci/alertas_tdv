"""
Servicio de logging de errores en Supabase.

Responsabilidad:
- Registrar errores críticos o recuperables del backend.
- No debe romper el flujo si Supabase falla.
- Se usa para depurar procesamiento de alertas.
"""

from typing import Any, Dict, Optional
import os
import traceback as traceback_module

from app.core.logging import log_event
from app.utils.json_utils import sanitize_for_json
from app.utils.math_utils import nested_get

try:
    from app.repositories.supabase_repo import (
        SUPABASE_RUNTIME_ENABLED,
        supabase,
    )
except Exception:
    SUPABASE_RUNTIME_ENABLED = False
    supabase = None


def build_error_log_row(
    stage: str,
    error: Exception | str,
    trace_id: str = "-",
    payload: Optional[Dict[str, Any]] = None,
    validation_payload: Optional[Dict[str, Any]] = None,
    route: Optional[str] = None,
    severity: str = "ERROR",
    context: Optional[Dict[str, Any]] = None,
    traceback_text: Optional[str] = None,
) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    validation_payload = validation_payload if isinstance(validation_payload, dict) else {}
    context = context if isinstance(context, dict) else {}

    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}

    error_type = type(error).__name__ if isinstance(error, Exception) else "Error"
    error_message = str(error)

    if traceback_text is None and isinstance(error, Exception):
        traceback_text = traceback_module.format_exc()

    return sanitize_for_json({
        "severity": severity,
        "service": "fastapi_trading_backend",
        "environment": os.getenv("APP_ENV", os.getenv("VERCEL_ENV", "unknown")),

        "route": route,
        "stage": stage,
        "trace_id": trace_id,

        "event_uid": payload.get("event_uid"),
        "message_type": payload.get("message_type"),
        "symbol": signal.get("symbol") or payload.get("symbol") or payload.get("ticker"),
        "timeframe": signal.get("tf") or payload.get("tf") or payload.get("timeframe"),
        "event": signal.get("event") or payload.get("event"),
        "side": signal.get("side") or payload.get("side"),

        "error_type": error_type,
        "error_message": error_message,
        "traceback": traceback_text,

        "request_payload": payload,
        "validation_payload": validation_payload,
        "context": {
            **context,
            "source_script": nested_get(payload, "source", "script"),
            "schema_version": payload.get("schema_version"),
        },
    })


async def persist_backend_error_log(
    stage: str,
    error: Exception | str,
    trace_id: str = "-",
    payload: Optional[Dict[str, Any]] = None,
    validation_payload: Optional[Dict[str, Any]] = None,
    route: Optional[str] = None,
    severity: str = "ERROR",
    context: Optional[Dict[str, Any]] = None,
    traceback_text: Optional[str] = None,
) -> bool:
    """
    Inserta un error en Supabase.

    Nunca debe lanzar excepción hacia arriba.
    Si Supabase falla, solo loguea en consola.
    """

    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        log_event("backend_error_log_skipped", {
            "reason": "supabase_not_configured",
            "stage": stage,
            "trace_id": trace_id,
            "error": str(error),
        })
        return False

    try:
        row = build_error_log_row(
            stage=stage,
            error=error,
            trace_id=trace_id,
            payload=payload,
            validation_payload=validation_payload,
            route=route,
            severity=severity,
            context=context,
            traceback_text=traceback_text,
        )

        supabase.table("backend_error_logs").insert(row).execute()

        log_event("backend_error_log_insert_ok", {
            "stage": stage,
            "trace_id": trace_id,
            "event_uid": row.get("event_uid"),
            "error_type": row.get("error_type"),
        })

        return True

    except Exception as insert_error:
        log_event("backend_error_log_insert_error", {
            "stage": stage,
            "trace_id": trace_id,
            "original_error": str(error),
            "insert_error": str(insert_error),
        })
        return False