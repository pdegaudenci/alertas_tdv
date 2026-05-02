"""
Servicio de procesamiento background del webhook.

Responsabilidad:
- Ejecutar validación en background.
- Actualizar LAST_VALIDATION.
- Enviar Telegram si la entrada queda aprobada.
- Persistir en Supabase.
- Exportar evento para Databricks/Lakehouse.
- Actualizar LAST_ALERT con validation y background_processed_at.
- Registrar errores de procesamiento en Supabase backend_error_logs.

IMPORTANTE:
- Este servicio puede ser reutilizado desde FastAPI, Lambda, scripts locales o tests.
- No depende de Request, BackgroundTasks ni Response.
- Devuelve un dict con estado para que Lambda/SQS pueda decidir si reintentar o no.

Regla de errores:
- Validación: crítico.
- Supabase: crítico.
- Export S3/Databricks: crítico.
- Telegram: no crítico.
- LAST_ALERT update: no crítico.
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
from app.services.error_log_service import persist_backend_error_log
from app.repositories.supabase_repo import persist_to_supabase


async def process_alert_background(payload: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    validation_result = None

    # ============================================================
    # 1. VALIDATION
    # ============================================================

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
                    "reason": [
                        f"validation_skipped_for_message_type:{payload.get('message_type')}"
                    ],
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

        await persist_backend_error_log(
            stage="bg_validation_error",
            error=e,
            trace_id=trace_id,
            payload=payload,
            validation_payload=validation_result,
            route="/api/webhook",
            context={
                "component": "webhook_background_service",
                "operation": "run_validation",
                "message_type": payload.get("message_type"),
                "event_uid": payload.get("event_uid"),
                "event": nested_get(payload, "signal", "event"),
                "side": nested_get(payload, "signal", "side"),
                "symbol": nested_get(payload, "signal", "symbol"),
            },
        )

        return {
            "ok": False,
            "critical_error": True,
            "stage": "bg_validation_error",
            "error": str(e),
            "validation": sanitize_for_json(LAST_VALIDATION),
        }

    # ============================================================
    # 2. TELEGRAM NOTIFICATION
    # ============================================================
    # No crítico: si falla Telegram, NO debe provocar retry completo de SQS.

    try:
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
        log_trace(trace_id, "bg_telegram_error_non_critical", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")

        await persist_backend_error_log(
            stage="bg_telegram_error_non_critical",
            error=e,
            trace_id=trace_id,
            payload=payload,
            validation_payload=LAST_VALIDATION,
            route="/api/webhook",
            context={
                "component": "webhook_background_service",
                "operation": "send_telegram_message",
                "message_type": payload.get("message_type"),
                "event_uid": payload.get("event_uid"),
                "event": nested_get(payload, "signal", "event"),
                "side": nested_get(payload, "signal", "side"),
                "symbol": nested_get(payload, "signal", "symbol"),
            },
        )

    # ============================================================
    # 3. SUPABASE PERSISTENCE
    # ============================================================

    try:
        t0_supabase = time.perf_counter()

        await persist_to_supabase(
            payload,
            LAST_VALIDATION,
            trace_id=trace_id,
        )

        supabase_ms = round((time.perf_counter() - t0_supabase) * 1000, 2)

        log_trace(trace_id, "bg_supabase_persist_done", {
            "ms": supabase_ms,
        })

    except Exception as e:
        log_trace(trace_id, "bg_supabase_persist_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")

        await persist_backend_error_log(
            stage="bg_supabase_persist_error",
            error=e,
            trace_id=trace_id,
            payload=payload,
            validation_payload=LAST_VALIDATION,
            route="/api/webhook",
            context={
                "component": "webhook_background_service",
                "operation": "persist_to_supabase",
                "message_type": payload.get("message_type"),
                "event_uid": payload.get("event_uid"),
                "event": nested_get(payload, "signal", "event"),
                "side": nested_get(payload, "signal", "side"),
                "symbol": nested_get(payload, "signal", "symbol"),
            },
        )

        return {
            "ok": False,
            "critical_error": True,
            "stage": "bg_supabase_persist_error",
            "error": str(e),
            "validation": sanitize_for_json(LAST_VALIDATION),
        }


    # ============================================================
    # 4. DATABRICKS / LAKEHOUSE EXPORT
    # ============================================================

    try:
        t0_databricks_export = time.perf_counter()

        databricks_export_result = export_event_for_databricks(
            payload=payload,
            validation=LAST_VALIDATION,
            trace_id=trace_id,
        )

        databricks_export_ms = round((time.perf_counter() - t0_databricks_export) * 1000, 2)

        if not isinstance(databricks_export_result, dict):
            raise RuntimeError({
                "stage": "bg_databricks_export_invalid_result",
                "error": "export_event_for_databricks returned non-dict result",
                "result_type": str(type(databricks_export_result)),
            })

        if databricks_export_result.get("ok") is not True:
            raise RuntimeError({
                "stage": "bg_databricks_export_failed",
                "result": databricks_export_result,
            })

        log_trace(trace_id, "bg_databricks_export_done", {
            "ms": databricks_export_ms,
            "result": databricks_export_result,
        })

    except Exception as e:
        log_trace(trace_id, "bg_databricks_export_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")

        await persist_backend_error_log(
            stage="bg_databricks_export_error",
            error=e,
            trace_id=trace_id,
            payload=payload,
            validation_payload=LAST_VALIDATION,
            route="/api/webhook",
            context={
                "component": "webhook_background_service",
                "operation": "export_event_for_databricks",
                "message_type": payload.get("message_type"),
                "event_uid": payload.get("event_uid"),
                "event": nested_get(payload, "signal", "event"),
                "side": nested_get(payload, "signal", "side"),
                "symbol": nested_get(payload, "signal", "symbol"),
            },
        )

        return {
            "ok": False,
            "critical_error": True,
            "stage": "bg_databricks_export_error",
            "error": str(e),
            "validation": sanitize_for_json(LAST_VALIDATION),
        }
    # ============================================================
    # 5. LAST_ALERT UPDATE
    # ============================================================
    # No crítico: si falla, no debe forzar retry SQS.

    try:
        if isinstance(LAST_ALERT, dict):
            LAST_ALERT["validation"] = sanitize_for_json(LAST_VALIDATION)
            LAST_ALERT["background_processed_at"] = utc_now_iso()

    except Exception as e:
        log_trace(trace_id, "bg_last_alert_update_error_non_critical", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")

        await persist_backend_error_log(
            stage="bg_last_alert_update_error_non_critical",
            error=e,
            trace_id=trace_id,
            payload=payload,
            validation_payload=LAST_VALIDATION,
            route="/api/webhook",
            context={
                "component": "webhook_background_service",
                "operation": "update_LAST_ALERT",
                "message_type": payload.get("message_type"),
                "event_uid": payload.get("event_uid"),
                "event": nested_get(payload, "signal", "event"),
                "side": nested_get(payload, "signal", "side"),
                "symbol": nested_get(payload, "signal", "symbol"),
            },
        )

    return {
        "ok": True,
        "critical_error": False,
        "stage": "completed",
        "validation": sanitize_for_json(LAST_VALIDATION),
    }