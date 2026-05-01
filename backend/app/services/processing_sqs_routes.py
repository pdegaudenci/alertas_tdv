"""
Rutas de procesamiento AWS SQS.

Endpoints:
- POST /api/process/sqs
- GET  /api/process/sqs/cron
- GET  /api/process/sqs/status

Flujo:
- /api/webhook encola en SQS.
- /api/process/sqs consume SQS.
- CORE/EXTRA se guardan en buffer Supabase hasta estar completos.
- process_alert_background() ejecuta validación, Supabase operativo, Telegram y export S3/Databricks.
"""

from typing import Optional, Dict, Any
import os
import traceback
import hmac
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.security import validate_secret
from app.core.logging import log_trace, make_trace_id
from app.core.state import LAST_VALIDATION

from app.utils.json_utils import sanitize_for_json

from app.services.alert_service import (
    merge_core_extra_payloads,
    ensure_canonical_schema,
)
from app.services.webhook_background_service import process_alert_background
from app.services.sqs_queue_service import (
    receive_sqs_messages,
    delete_sqs_message,
    get_sqs_queue_status,
)
from app.services.sqs_fragment_store_service import (
    upsert_fragment_payload,
    mark_fragment_processed,
    mark_fragment_error,
)
from app.services.error_log_service import persist_backend_error_log


router = APIRouter()


SPLIT_TYPES = {
    "logical_event_core",
    "logical_event_extra",
}


def _get_payload_message_type(payload: Dict[str, Any]) -> str:
    return str(payload.get("message_type") or "").lower().strip()


def _get_payload_event_uid(payload: Dict[str, Any]) -> str:
    return str(payload.get("event_uid") or "").strip()

def _validate_cron_secret(request: Request) -> None:
    expected = (os.getenv("CRON_SECRET") or "").strip()

    if not expected:
        raise HTTPException(
            status_code=500,
            detail="CRON_SECRET not configured",
        )

    auth_header = (request.headers.get("authorization") or "").strip()
    expected_header = f"Bearer {expected}"

    if not hmac.compare_digest(auth_header, expected_header):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized cron request",
        )

async def _process_sqs_alerts_internal(
    limit: int,
    trace_id: str,
) -> Dict[str, Any]:
    processed = []
    failed = []
    buffered = []
    ready_processed = []

    messages = await receive_sqs_messages(
        trace_id=trace_id,
        max_messages=limit,
    )

    for msg in messages:
        receipt_handle = msg.get("receipt_handle")
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}

        message_type = _get_payload_message_type(payload)
        event_uid = _get_payload_event_uid(payload)

        if not payload:
            failed.append({
                "message_id": msg.get("message_id"),
                "error": "empty_payload",
            })
            continue

        # ========================================================
        # A. CORE / EXTRA: guardar fragmento en Supabase buffer
        # ========================================================

        if message_type in SPLIT_TYPES:
            try:
                fragment_result = await upsert_fragment_payload(
                    payload=payload,
                    trace_id=trace_id,
                )

                if not fragment_result.get("ok"):
                    raise RuntimeError(fragment_result.get("error") or fragment_result.get("reason") or "fragment_upsert_failed")

                # Una vez guardado el fragmento, borramos el mensaje de SQS.
                # Ya no dependemos de que SQS mantenga este fragmento.
                await delete_sqs_message(
                    receipt_handle=receipt_handle,
                    trace_id=trace_id,
                )

                buffered.append({
                    "event_uid": event_uid,
                    "message_type": message_type,
                    "complete": fragment_result.get("complete"),
                })

                # Si ya están CORE + EXTRA, ensamblamos y procesamos.
                if fragment_result.get("complete"):
                    row = fragment_result.get("row") or {}
                    core_payload = row.get("core_payload") or {}
                    extra_payload = row.get("extra_payload") or {}

                    merged_payload = merge_core_extra_payloads(
                        core=core_payload,
                        extra=extra_payload,
                    )

                    merged_payload = ensure_canonical_schema(merged_payload)

                    processed_item = await _process_full_payload(
                        payload=merged_payload,
                        trace_id=trace_id,
                        source="sqs_core_extra_buffer",
                    )

                    await mark_fragment_processed(
                        event_uid=event_uid,
                        merged_payload=merged_payload,
                        validation_payload=LAST_VALIDATION,
                        trace_id=trace_id,
                    )

                    ready_processed.append(processed_item)
                    processed.append(processed_item)

            except Exception as e:
                failed.append({
                    "event_uid": event_uid,
                    "message_type": message_type,
                    "error": str(e),
                })

                if event_uid:
                    await mark_fragment_error(
                        event_uid=event_uid,
                        error=e,
                        trace_id=trace_id,
                    )

                await persist_backend_error_log(
                    stage="process_sqs_fragment_error",
                    error=e,
                    trace_id=trace_id,
                    payload=payload,
                    validation_payload=LAST_VALIDATION,
                    route="/api/process/sqs",
                    context={
                        "component": "processing_sqs_routes",
                        "operation": "process_split_fragment",
                        "event_uid": event_uid,
                        "message_type": message_type,
                        "traceback": traceback.format_exc(),
                    },
                )

                # No borramos de SQS si ni siquiera pudo guardarse/procesarse.
                continue

            continue

        # ========================================================
        # B. Mensajes completos: logical_event_full / executed_event
        # ========================================================

        try:
            processed_item = await _process_full_payload(
                payload=payload,
                trace_id=trace_id,
                source="sqs_single_message",
            )

            await delete_sqs_message(
                receipt_handle=receipt_handle,
                trace_id=trace_id,
            )

            processed.append(processed_item)

        except Exception as e:
            failed.append({
                "event_uid": event_uid,
                "message_type": message_type,
                "error": str(e),
            })

            await persist_backend_error_log(
                stage="process_sqs_single_error",
                error=e,
                trace_id=trace_id,
                payload=payload,
                validation_payload=LAST_VALIDATION,
                route="/api/process/sqs",
                context={
                    "component": "processing_sqs_routes",
                    "operation": "process_single_message",
                    "event_uid": event_uid,
                    "message_type": message_type,
                    "traceback": traceback.format_exc(),
                },
            )

            # No borrar de SQS. AWS reintentará y luego DLQ si falla varias veces.
            continue

    return sanitize_for_json({
        "ok": True,
        "trace_id": trace_id,
        "received_count": len(messages),
        "buffered_count": len(buffered),
        "ready_processed_count": len(ready_processed),
        "processed_count": len(processed),
        "failed_count": len(failed),
        "buffered": buffered,
        "processed": processed,
        "failed": failed,
    })


@router.post("/api/process/sqs")
async def process_sqs_alerts(
    limit: int = 10,
    x_webhook_secret: Optional[str] = Header(default=None),
):
    validate_secret(x_webhook_secret=x_webhook_secret)

    trace_id = make_trace_id()

    try:
        response = await _process_sqs_alerts_internal(
            limit=limit,
            trace_id=trace_id,
        )

        log_trace(trace_id, "process_sqs_done", response)

        return JSONResponse(
            status_code=200,
            content=response,
        )

    except HTTPException:
        raise

    except Exception as e:
        await persist_backend_error_log(
            stage="process_sqs_unhandled_error",
            error=e,
            trace_id=trace_id,
            route="/api/process/sqs",
            context={
                "component": "processing_sqs_routes",
                "operation": "process_sqs_alerts",
                "traceback": traceback.format_exc(),
            },
        )

        return JSONResponse(
            status_code=500,
            content=sanitize_for_json({
                "ok": False,
                "trace_id": trace_id,
                "error": str(e),
            }),
        )


@router.get("/api/process/sqs/cron")
async def process_sqs_alerts_cron(
    request: Request,
    limit: int = 10,
):
    _validate_cron_secret(request)

    trace_id = make_trace_id()

    try:
        safe_limit = max(1, min(int(limit), 10))

        response = await _process_sqs_alerts_internal(
            limit=safe_limit,
            trace_id=trace_id,
        )

        response = sanitize_for_json(response)

        log_trace(trace_id, "process_sqs_cron_done", response)

        return JSONResponse(
            status_code=200,
            content=response,
        )

    except HTTPException:
        raise

    except Exception as e:
        await persist_backend_error_log(
            stage="process_sqs_cron_unhandled_error",
            error=e,
            trace_id=trace_id,
            route="/api/process/sqs/cron",
            context={
                "component": "processing_sqs_routes",
                "operation": "process_sqs_alerts_cron",
                "traceback": traceback.format_exc(),
            },
        )

        return JSONResponse(
            status_code=500,
            content=sanitize_for_json({
                "ok": False,
                "trace_id": trace_id,
                "error": str(e),
            }),
        )
@router.get("/api/process/sqs/status")
async def process_sqs_status(
    x_webhook_secret: Optional[str] = Header(default=None),
):
    validate_secret(x_webhook_secret=x_webhook_secret)

    trace_id = make_trace_id()

    status = await get_sqs_queue_status(trace_id=trace_id)

    return JSONResponse(
        status_code=200 if status.get("ok") else 500,
        content=sanitize_for_json({
            "trace_id": trace_id,
            **status,
        }),
    )