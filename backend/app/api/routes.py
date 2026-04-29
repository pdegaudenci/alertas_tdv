"""
Rutas FastAPI del backend TradingView Validation Layer.

Endpoints:
- /
- /api/latest
- /api/validation/latest
- /api/validate
- /api/webhook
- /api/alerts
- /api/health/binance
- /api/health/supabase
- /api/alerts/supabase
- /api/setups/supabase


"""

from typing import Optional, Dict, Any
import time
import traceback

from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.state.memory import LAST_ALERT, LAST_VALIDATION, ALERT_HISTORY
from app.utils.serialization import utc_now_iso, sanitize_for_json
from app.core.config import (
    BINANCE_BASE_URLS,
    SUPABASE_ENABLED,
    supabase,
)
from app.core.logger import log_event, log_trace, make_trace_id
from app.services.alert_schema_service import (
    parse_payload,
    validate_secret,
    assemble_event_payload,
    should_validate_payload,
    nested_get,
)
from app.services.validation_service import run_validation
from app.services.market_data_service import fetch_depth
from app.services.supabase_service import (
    persist_to_supabase,
)
from app.services.telegram_service import (
    send_telegram_message,
    build_telegram_entry_message,
)
from app.services.assembler_service import (
    assemble_core_extra_by_event_uid,
)
from app.services.history_service import build_history_item
from app.services.supabase_read_service import (
    get_alerts_supabase_service,
    get_setups_supabase_service,
)

router = APIRouter()


# ============================================================
# ROOT
# ============================================================

@router.get("/")
async def healthcheck():
    return {
        "ok": True,
        "service": "tradingview-validation-layer",
        "timestamp": utc_now_iso(),
        "routes": [
            "/",
            "/api/latest",
            "/api/webhook",
            "/api/validate",
            "/api/health/binance",
        ],
        "binance_base_urls": BINANCE_BASE_URLS,
    }


# ============================================================
# MEMORY STATE
# ============================================================

@router.get("/api/latest")
async def latest_alert():
    return LAST_ALERT


@router.get("/api/validation/latest")
async def get_latest_validation():
    return LAST_VALIDATION


@router.get("/api/alerts")
async def get_alerts(limit: int = 50):
    items = list(ALERT_HISTORY)[-limit:]
    items.reverse()

    return {
        "ok": True,
        "count": len(items),
        "items": items,
    }


# ============================================================
# HEALTH
# ============================================================

@router.get("/api/health/binance")
async def health_binance():
    try:
        depth = await fetch_depth("BTCUSDC", 5)

        return {
            "ok": True,
            "timestamp": utc_now_iso(),
            "symbol_tested": "BTCUSDC",
            "depth_keys": list(depth.keys()),
        }

    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "timestamp": utc_now_iso(),
                "error": str(e),
            },
        )


@router.get("/api/health/supabase")
async def health_supabase():
    if not SUPABASE_ENABLED or supabase is None:
        return {
            "ok": False,
            "enabled": False,
            "message": "Supabase not configured",
        }

    try:
        resp = supabase.table("trade_setups").select("id", count="exact").limit(1).execute()

        return {
            "ok": True,
            "enabled": True,
            "message": "Supabase connection OK",
            "sample_count": resp.count,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "enabled": True,
                "message": "Supabase connection failed",
                "error": str(e),
            },
        )


# ============================================================
# MANUAL VALIDATE
# ============================================================

@router.post("/api/validate")
async def validate_payload(
    request: Request,
    x_webhook_secret: Optional[str] = Header(default=None),
):
    validate_secret(x_webhook_secret)

    raw_body = await request.body()
    payload = parse_payload(raw_body)

    if not payload:
        if LAST_ALERT.get("payload"):
            payload = LAST_ALERT["payload"]
        else:
            raise HTTPException(status_code=400, detail="Empty payload and no LAST_ALERT stored")

    result = await run_validation(payload)
    safe_result = sanitize_for_json(result)

    log_event("validate_endpoint_response", safe_result)

    return JSONResponse(status_code=200, content=safe_result)


# ============================================================
# WEBHOOK
# ============================================================

@router.post("/api/webhook")
async def tradingview_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: Optional[str] = Header(default=None),
):
    global LAST_ALERT, LAST_VALIDATION

    async def process_alert_background(payload: Dict[str, Any], trace_id: str):
        global LAST_ALERT, LAST_VALIDATION

        validation_result = None

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------
        try:
            if should_validate_payload(payload):
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

            LAST_VALIDATION.clear()
            LAST_VALIDATION.update(sanitize_for_json(validation_result))

            validation_block = LAST_VALIDATION.get("validation", {})

            if validation_block.get("approve") is True:
                telegram_text = build_telegram_entry_message(LAST_VALIDATION)
                send_telegram_message(telegram_text, trace_id=trace_id)

        except Exception as e:
            LAST_VALIDATION.clear()
            LAST_VALIDATION.update(
                sanitize_for_json(
                    {
                        "ok": False,
                        "validated_at": utc_now_iso(),
                        "message": "Validation failed in background",
                        "error": str(e),
                    }
                )
            )

            log_trace(
                trace_id,
                "bg_validation_error",
                {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
                level="ERROR",
            )

        # ----------------------------------------------------
        # SUPABASE
        # ----------------------------------------------------
        try:
            await persist_to_supabase(payload, LAST_VALIDATION, trace_id=trace_id)

        except Exception as e:
            log_trace(
                trace_id,
                "bg_supabase_error",
                {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
                level="ERROR",
            )

        # ----------------------------------------------------
        # UPDATE LAST ALERT
        # ----------------------------------------------------
        try:
            LAST_ALERT["validation"] = LAST_VALIDATION
            LAST_ALERT["background_processed_at"] = utc_now_iso()

        except Exception:
            pass

    # ========================================================
    # MAIN REQUEST
    # ========================================================
    try:
        t0_total = time.perf_counter()
        trace_id = make_trace_id()

        validate_secret(x_webhook_secret)

        raw_body = await request.body()
        payload_raw = parse_payload(raw_body)
        payload_raw = assemble_event_payload(payload_raw)

        payload, payload_complete = assemble_core_extra_by_event_uid(payload_raw)

        signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
        context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
        quality = payload.get("quality", {}) if isinstance(payload.get("quality"), dict) else {}
        htf_context = payload.get("htf_context", {}) if isinstance(payload.get("htf_context"), dict) else {}

        # Placeholder validation
        LAST_VALIDATION.clear()
        LAST_VALIDATION.update(
            sanitize_for_json(
                {
                    "ok": True,
                    "validated_at": utc_now_iso(),
                    "message": "Validation queued in background",
                    "validation": {
                        "approve": False,
                        "confidence": 0,
                        "probability_tp_before_sl": None,
                        "score_external": None,
                        "reason": ["validation_queued_background"],
                        "penalties": [],
                        "event_type": signal.get("event"),
                    },
                }
            )
        )

        LAST_ALERT.clear()
        LAST_ALERT.update(
            sanitize_for_json(
                {
                    "ok": True,
                    "received_at": utc_now_iso(),
                    "route": "/api/webhook",
                    "processing_mode": "fast_ack_background",
                    "trace_id": trace_id,
                    "schema_version": payload.get("schema_version"),
                    "message_type": payload.get("message_type"),
                    "event_uid": payload.get("event_uid"),
                    "symbol": signal.get("symbol"),
                    "timeframe": signal.get("tf"),
                    "event": signal.get("event"),
                    "setup": signal.get("setup"),
                    "phase": context.get("phase"),
                    "regime": context.get("regime"),
                    "strength": context.get("phase_strength"),
                    "phase_5m": htf_context.get("htf_phase"),
                    "strength_5m": htf_context.get("htf_phase_strength"),
                    "quality_score": quality.get("quality_score"),
                    "price": signal.get("price"),
                    "side": signal.get("side"),
                    "payload": payload,
                    "validation": LAST_VALIDATION,
                }
            )
        )

        # Partial CORE / EXTRA waiting
        if not payload_complete:
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "message": "Partial payload received. Waiting for matching CORE/EXTRA.",
                    "event_uid": payload.get("event_uid"),
                    "message_type": payload.get("message_type"),
                },
            )

        # History
        ALERT_HISTORY.append(
            sanitize_for_json(
                build_history_item(payload, LAST_VALIDATION)
            )
        )

        # Background task
        background_tasks.add_task(process_alert_background, payload, trace_id)

        total_ms = round((time.perf_counter() - t0_total) * 1000, 2)

        response_content = {
            "ok": True,
            "message": "Alert received quickly. Validation, Supabase and Telegram queued in background.",
            "trace_id": trace_id,
            "processing_ms": total_ms,
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
            "event": signal.get("event"),
            "side": signal.get("side"),
            "symbol": signal.get("symbol"),
        }

        return JSONResponse(status_code=200, content=sanitize_for_json(response_content))

    except HTTPException as e:
        raise e

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=sanitize_for_json(
                {
                    "ok": False,
                    "message": "Unhandled webhook processing error",
                    "error": str(e),
                    "received_at": utc_now_iso(),
                }
            ),
        )


# ============================================================
# SUPABASE READ ENDPOINTS
# ============================================================

@router.get("/api/alerts/supabase")
async def get_alerts_supabase(limit: int = 50):
    return await get_alerts_supabase_service(limit)


@router.get("/api/setups/supabase")
async def get_setups_supabase(limit: int = 50):
    return await get_setups_supabase_service(limit)


# ============================================================
# ROOT POST ALIAS
# ============================================================

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