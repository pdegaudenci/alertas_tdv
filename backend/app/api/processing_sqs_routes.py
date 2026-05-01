"""
Rutas de procesamiento AWS SQS.

Endpoints:
- POST /api/process/sqs
- GET  /api/process/sqs/status

Objetivo:
Procesar alertas desde SQS sin bloquear TradingView.
"""

from typing import Optional, Dict, Any, List
import traceback

from fastapi import APIRouter, Header, HTTPException
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
    change_sqs_message_visibility,
    get_sqs_queue_status,
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


def _group_split_messages(messages: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    grouped: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for msg in messages:
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
        message_type = _get_payload_message_type(payload)
        event_uid = _get_payload_event_uid(payload)

        if message_type not in SPLIT_TYPES:
            continue

        if not event_uid:
            continue

        if event_uid not in grouped:
            grouped[event_uid] = {}

        grouped[event_uid][message_type] = msg

    return grouped


@router.post("/api/process/sqs")
async def process_sqs_alerts(
    limit: int = 10,
    x_webhook_secret: Optional[str] = Header(default=None),
):
    """
    Lee mensajes desde SQS y procesa alertas.

    Recomendado:
    - Ejecutarlo manualmente desde Postman para pruebas.
    - Luego con Vercel Cron cada 1 minuto.
    """

    validate_secret(x_webhook_secret)

    trace_id = make_trace_id()

    processed = []
    failed = []
    waiting_for_pair = []

    try:
        messages = await receive_sqs_messages(
            trace_id=trace_id,
            max_messages=limit,
        )

        grouped_pairs = _group_split_messages(messages)

        consumed_receipts = set()

        # ========================================================
        # 1. Procesar pares CORE + EXTRA recibidos en el mismo batch
        # ========================================================

        for event_uid, parts in grouped_pairs.items():
            core_msg = parts.get("logical_event_core")
            extra_msg = parts.get("logical_event_extra")

            if not core_msg or not extra_msg:
                waiting_for_pair.append({
                    "event_uid": event_uid,
                    "available_parts": list(parts.keys()),
                })
                continue

            core_payload = core_msg.get("payload") or {}
            extra_payload = extra_msg.get("payload") or {}

            try:
                merged_payload = merge_core_extra_payloads(
                    core=core_payload,
                    extra=extra_payload,
                )

                merged_payload = ensure_canonical_schema(merged_payload)

                await process_alert_background(
                    payload=merged_payload,
                    trace_id=trace_id,
                )

                await delete_sqs_message(
                    receipt_handle=core_msg["receipt_handle"],
                    trace_id=trace_id,
                )

                await delete_sqs_message(
                    receipt_handle=extra_msg["receipt_handle"],
                    trace_id=trace_id,
                )

                consumed_receipts.add(core_msg["receipt_handle"])
                consumed_receipts.add(extra_msg["receipt_handle"])

                processed.append({
                    "event_uid": event_uid,
                    "message_type": "logical_event_full",
                    "processed_from": [
                        "logical_event_core",
                        "logical_event_extra",
                    ],
                    "validation": LAST_VALIDATION,
                })

            except Exception as e:
                failed.append({
                    "event_uid": event_uid,
                    "message_type": "logical_event_full",
                    "error": str(e),
                })

                await persist_backend_error_log(
                    stage="process_sqs_pair_error",
                    error=e,
                    trace_id=trace_id,
                    payload={
                        "core": core_payload,
                        "extra": extra_payload,
                    },
                    validation_payload=LAST_VALIDATION,
                    route="/api/process/sqs",
                    context={
                        "component": "processing_sqs_routes",
                        "operation": "process_core_extra_pair",
                        "event_uid": event_uid,
                        "traceback": traceback.format_exc(),
                    },
                )

                # No borramos mensajes. SQS reintentará.
                continue

        # ========================================================
        # 2. Procesar mensajes completos no split
        # ========================================================

        for msg in messages:
            receipt_handle = msg.get("receipt_handle")

            if receipt_handle in consumed_receipts:
                continue

            payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
            message_type = _get_payload_message_type(payload)
            event_uid = _get_payload_event_uid(payload)

            if message_type in SPLIT_TYPES:
                # No borrar. Espera a que llegue el otro fragmento.
                await change_sqs_message_visibility(
                    receipt_handle=receipt_handle,
                    visibility_timeout=30,
                    trace_id=trace_id,
                )
                continue

            try:
                payload = ensure_canonical_schema(payload)

                await process_alert_background(
                    payload=payload,
                    trace_id=trace_id,
                )

                await delete_sqs_message(
                    receipt_handle=receipt_handle,
                    trace_id=trace_id,
                )

                consumed_receipts.add(receipt_handle)

                processed.append({
                    "event_uid": event_uid,
                    "message_type": message_type,
                    "processed_from": ["single_message"],
                    "validation": LAST_VALIDATION,
                })

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

                # No borrar. SQS reintentará y si supera maxReceiveCount irá a DLQ.
                continue

        response = sanitize_for_json({
            "ok": True,
            "trace_id": trace_id,
            "received_count": len(messages),
            "processed_count": len(processed),
            "failed_count": len(failed),
            "waiting_for_pair_count": len(waiting_for_pair),
            "processed": processed,
            "failed": failed,
            "waiting_for_pair": waiting_for_pair,
        })

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


@router.get("/api/process/sqs/status")
async def process_sqs_status(
    x_webhook_secret: Optional[str] = Header(default=None),
):
    validate_secret(x_webhook_secret)

    trace_id = make_trace_id()

    status = await get_sqs_queue_status(trace_id=trace_id)

    return JSONResponse(
        status_code=200 if status.get("ok") else 500,
        content=sanitize_for_json({
            "trace_id": trace_id,
            **status,
        }),
    )