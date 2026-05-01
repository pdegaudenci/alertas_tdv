"""
Rutas webhook TradingView.

Endpoints:
- /api/webhook
- /

Modo anti-timeout:
- Recibe alerta.
- Valida secret desde header o payload.secret.
- Responde rápido a TradingView.
- Envía payload a AWS SQS en background.
- NO ejecuta validación/Supabase/S3/Telegram en el request.
"""

from typing import Optional
import time
import traceback

from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.core.state import LAST_VALIDATION, ALERT_HISTORY
from app.core.security import validate_secret
from app.core.logging import log_event, log_trace, make_trace_id

from app.utils.time_utils import utc_now_iso
from app.utils.json_utils import sanitize_for_json
from app.utils.math_utils import nested_get

from app.services.webhook_state_service import (
    set_validation_queued,
    set_last_alert_fast_ack,
    set_last_alert_partial,
)
from app.services.alert_service import (
    parse_payload,
    assemble_event_payload,
    build_history_item,
)
from app.services.sqs_queue_service import send_alert_to_sqs
from app.services.error_log_service import persist_backend_error_log


router = APIRouter()


async def enqueue_sqs_background(payload: dict, trace_id: str) -> None:
    """
    Envía a SQS fuera del camino crítico del webhook.

    Importante:
    - TradingView ya recibió 200 antes de que esto termine.
    - Si falla, se registra en backend_error_logs.
    """

    try:
        result = await send_alert_to_sqs(
            payload=payload,
            trace_id=trace_id,
            source="tradingview_webhook_background",
        )

        if not result.get("ok"):
            await persist_backend_error_log(
                stage="sqs_enqueue_background_failed",
                error=result.get("error") or result.get("reason") or "SQS enqueue failed",
                trace_id=trace_id,
                payload=payload,
                route="/api/webhook",
                context={
                    "component": "webhook_routes",
                    "operation": "enqueue_sqs_background",
                    "sqs_result": result,
                },
            )

    except Exception as e:
        log_trace(trace_id, "sqs_enqueue_background_exception", {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
        }, level="ERROR")

        await persist_backend_error_log(
            stage="sqs_enqueue_background_exception",
            error=e,
            trace_id=trace_id,
            payload=payload,
            route="/api/webhook",
            context={
                "component": "webhook_routes",
                "operation": "enqueue_sqs_background",
                "traceback": traceback.format_exc(),
            },
        )


@router.post("/api/webhook")
async def tradingview_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: Optional[str] = Header(default=None),
):
    try:
        t0_total = time.perf_counter()
        trace_id = make_trace_id()

        log_trace(trace_id, "webhook_received_start", {
            "path": str(request.url.path),
            "method": request.method,
            "query_params": dict(request.query_params),
            "client": request.client.host if request.client else None,
            "mode": "fast_ack_sqs_background",
        })

        raw_body = await request.body()
        raw_text = raw_body.decode("utf-8", errors="replace")

        t0_parse = time.perf_counter()

        payload_raw = parse_payload(raw_body)
        payload = assemble_event_payload(payload_raw)

        parse_ms = round((time.perf_counter() - t0_parse) * 1000, 2)

        validate_secret(
            x_webhook_secret=x_webhook_secret,
            payload_secret=payload.get("secret"),
        )

        debug_mode = str(request.query_params.get("debug", "0")).lower() in {
            "1",
            "true",
            "yes",
        }

        if debug_mode:
            return JSONResponse(
                status_code=200,
                content=sanitize_for_json({
                    "ok": True,
                    "message": "Webhook debug echo",
                    "received_at": utc_now_iso(),
                    "raw_body_text": raw_text,
                    "payload": payload,
                }),
            )

        log_trace(trace_id, "payload_parsed", {
            "parse_ms": parse_ms,
            "schema_version": payload.get("schema_version"),
            "message_type": payload.get("message_type"),
            "event_uid": payload.get("event_uid"),
            "event": nested_get(payload, "signal", "event"),
            "side": nested_get(payload, "signal", "side"),
            "symbol": nested_get(payload, "signal", "symbol"),
            "secret_present": bool(payload.get("secret")),
            "header_secret_present": bool(x_webhook_secret),
        })

        signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
        message_type = str(payload.get("message_type") or "").lower()

        set_validation_queued(payload)
        set_last_alert_fast_ack(payload, trace_id)

        if message_type in {"logical_event_core", "logical_event_extra"}:
            set_last_alert_partial(payload)

        history_item = sanitize_for_json(build_history_item(payload, LAST_VALIDATION))
        ALERT_HISTORY.append(history_item)

        background_tasks.add_task(
            enqueue_sqs_background,
            payload,
            trace_id,
        )

        total_ms = round((time.perf_counter() - t0_total) * 1000, 2)

        response_content = sanitize_for_json({
            "ok": True,
            "message": "Alert accepted quickly. SQS enqueue scheduled in background.",
            "trace_id": trace_id,
            "processing_ms": total_ms,
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
            "event": signal.get("event") or payload.get("event"),
            "side": signal.get("side") or payload.get("side"),
            "symbol": signal.get("symbol") or payload.get("symbol") or payload.get("ticker"),
            "queue_backend": "sqs",
            "background_processing": True,
            "processing_mode": "fast_ack_sqs_background",
        })

        log_trace(trace_id, "webhook_fast_response_sent", response_content)

        return JSONResponse(
            status_code=200,
            content=response_content,
        )

    except HTTPException as e:
        log_event("webhook_http_exception", {
            "status_code": e.status_code,
            "detail": e.detail,
            "traceback": traceback.format_exc(),
        })
        raise

    except Exception as e:
        error_response = sanitize_for_json({
            "ok": False,
            "message": "Unhandled webhook processing error",
            "error": str(e),
            "received_at": utc_now_iso(),
        })

        log_event("webhook_unhandled_exception", {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "response": error_response,
        })

        await persist_backend_error_log(
            stage="webhook_unhandled_exception",
            error=e,
            trace_id=trace_id if "trace_id" in locals() else "-",
            payload=payload if "payload" in locals() and isinstance(payload, dict) else {},
            route="/api/webhook",
            context={
                "component": "webhook_routes",
                "operation": "tradingview_webhook",
                "response": error_response,
            },
        )

        return JSONResponse(status_code=500, content=error_response)


@router.post("/")
async def root_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: Optional[str] = Header(default=None),
):
    return await tradingview_webhook(
        request=request,
        background_tasks=background_tasks,
        x_webhook_secret=x_webhook_secret,
    )