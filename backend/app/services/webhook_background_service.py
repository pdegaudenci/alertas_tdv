"""
Servicio de procesamiento background del webhook.

Responsabilidad:
- Ejecutar validación en background.
- Actualizar LAST_VALIDATION.
- Enviar Telegram si la entrada queda aprobada.
- Persistir en Supabase.
- Exportar evento para Databricks/Lakehouse.
- Actualizar LAST_ALERT con validation y background_processed_at.

Este servicio no cambia la lógica existente; solo mueve el bloque interno
process_alert_background fuera de webhook_routes.py.
"""

from typing import Any, Dict
import time
import traceback

from app.core.state import LAST_ALERT, LAST_VALIDATION
from app.core.logging import log_trace

from app.utils.time_utils import utc_now_iso
from app.utils.json_utils import sanitize_for_json
from app.utils.math_utils import nested_get

from app.services.alert_service import should_validate_payload
from app.services.validation_service import run_validation
from app.services.telegram_service import (
    send_telegram_message,
    build_telegram_entry_message,
)
from app.services.databricks_export_service import export_event_for_databricks
from app.repositories.supabase_repo import persist_to_supabase


async def process_alert_background(payload: Dict[str, Any], trace_id: str) -> None:
    validation_result = None

    try:
        t0_validation = time.perf_counter()

        if should_validate_payload(payload):
            log_trace(trace_id, "bg_validation_start", {
                "message_type": payload.get("message_type"),
                "event_uid": payload.get("event_uid"),
                "event": nested_get(payload, "signal", "event"),
                "side": nested_get(payload, "signal", "side"),
                "symbol": nested_get(payload, "signal", "symbol"),
            })

            validation_result = await run_validation(payload)

        else:
            validation_result = {
                "ok": True,
                "validated_at": utc_now_iso(),
                "message": "Validation skipped for non-entry event",
                "validation": {
                    "approve": False,
                    "confidence": 0,
                    "probability_tp_before_sl": None,
                    "score_external": None,
                    "reason": [f"validation_skipped_for_message_type:{payload.get('message_type')}"],
                    "penalties": [],
                    "event_type": nested_get(payload, "signal", "event"),
                },
            }

        validation_ms = round((time.perf_counter() - t0_validation) * 1000, 2)

        log_trace(trace_id, "bg_validation_done", {
            "ms": validation_ms,
            "validation_result": validation_result,
        })

        LAST_VALIDATION.clear()
        LAST_VALIDATION.update(sanitize_for_json(validation_result))

        validation_block = LAST_VALIDATION.get("validation", {}) if isinstance(LAST_VALIDATION, dict) else {}

        if validation_block.get("approve") is True:
            telegram_text = build_telegram_entry_message(LAST_VALIDATION)
            send_telegram_message(telegram_text, trace_id=trace_id)
        else:
            log_trace(trace_id, "telegram_not_sent", {
                "reason": "entry_not_approved",
                "approve": validation_block.get("approve"),
                "confidence": validation_block.get("confidence"),
            })

    except Exception as e:
        validation_result = {
            "ok": False,
            "validated_at": utc_now_iso(),
            "message": "Validation failed in background",
            "error": str(e),
        }

        LAST_VALIDATION.clear()
        LAST_VALIDATION.update(sanitize_for_json(validation_result))

        log_trace(trace_id, "bg_validation_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")

    try:
        t0_supabase = time.perf_counter()
        await persist_to_supabase(payload, LAST_VALIDATION, trace_id=trace_id)
        supabase_ms = round((time.perf_counter() - t0_supabase) * 1000, 2)

        log_trace(trace_id, "bg_supabase_persist_done", {
            "ms": supabase_ms,
        })

    except Exception as e:
        log_trace(trace_id, "bg_supabase_persist_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")

    try:
        t0_databricks_export = time.perf_counter()

        databricks_export_result = export_event_for_databricks(
            payload=payload,
            validation=LAST_VALIDATION,
            trace_id=trace_id,
        )

        databricks_export_ms = round((time.perf_counter() - t0_databricks_export) * 1000, 2)

        log_trace(trace_id, "bg_databricks_export_done", {
            "ms": databricks_export_ms,
            "result": databricks_export_result,
        })

    except Exception as e:
        log_trace(trace_id, "bg_databricks_export_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")

    try:
        if isinstance(LAST_ALERT, dict):
            LAST_ALERT["validation"] = LAST_VALIDATION
            LAST_ALERT["background_processed_at"] = utc_now_iso()

    except Exception as e:
        log_trace(trace_id, "bg_last_alert_update_error", {
            "error": str(e),
        })