"""
Rutas webhook TradingView.

Endpoints:
- /api/webhook
- /
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
    assemble_core_extra_by_event_uid,
    build_history_item,
)
from app.services.webhook_background_service import process_alert_background
from app.services.error_log_service import persist_backend_error_log

router = APIRouter()


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
        })

        validate_secret(x_webhook_secret)

        raw_body = await request.body()
        raw_text = raw_body.decode("utf-8", errors="replace")

        debug_mode = str(request.query_params.get("debug", "0")).lower() in {"1", "true", "yes"}

        if debug_mode:
            return JSONResponse(
                status_code=200,
                content=sanitize_for_json({
                    "ok": True,
                    "message": "Webhook debug echo",
                    "received_at": utc_now_iso(),
                    "raw_body_text": raw_text,
                }),
            )

        t0_parse = time.perf_counter()

        payload_raw = parse_payload(raw_body)
        payload_raw = assemble_event_payload(payload_raw)

        payload, payload_complete = assemble_core_extra_by_event_uid(payload_raw)

        parse_ms = round((time.perf_counter() - t0_parse) * 1000, 2)

        log_trace(trace_id, "payload_parsed", {
            "parse_ms": parse_ms,
            "message_type": payload.get("message_type"),
            "event_uid": payload.get("event_uid"),
            "event": nested_get(payload, "signal", "event"),
            "side": nested_get(payload, "signal", "side"),
            "symbol": nested_get(payload, "signal", "symbol"),
        })

        signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}

        set_validation_queued(payload)
        set_last_alert_fast_ack(payload, trace_id)
        if not payload_complete:
            set_last_alert_partial(payload)

            return JSONResponse(
                status_code=200,
                content=sanitize_for_json({
                    "ok": True,
                    "message": "Partial payload received. Waiting for matching CORE/EXTRA.",
                    "event_uid": payload.get("event_uid"),
                    "message_type": payload.get("message_type"),
                }),
            )

        history_item = sanitize_for_json(build_history_item(payload, LAST_VALIDATION))
        ALERT_HISTORY.append(history_item)

        background_tasks.add_task(process_alert_background, payload, trace_id)

        total_ms = round((time.perf_counter() - t0_total) * 1000, 2)

        response_content = sanitize_for_json({
            "ok": True,
            "message": "Alert received quickly. Validation, Supabase and Telegram queued in background.",
            "trace_id": trace_id,
            "processing_ms": total_ms,
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
            "event": signal.get("event") or payload.get("event"),
            "side": signal.get("side") or payload.get("side"),
            "symbol": signal.get("symbol") or payload.get("symbol") or payload.get("ticker"),
        })

        log_trace(trace_id, "webhook_fast_response_sent", response_content)

        return JSONResponse(status_code=200, content=response_content)

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