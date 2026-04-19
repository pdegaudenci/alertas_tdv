from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import os
import json
from datetime import datetime, timezone

app = FastAPI(title="TradingView Webhook Receiver")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_payload(raw_body: bytes) -> dict:
    text_body = raw_body.decode("utf-8", errors="replace").strip()

    if not text_body:
        return {}

    try:
        parsed = json.loads(text_body)
        if isinstance(parsed, dict):
            return parsed
        return {"raw_json": parsed}
    except json.JSONDecodeError:
        return {"raw_message": text_body}


def build_log(route: str, payload: dict, headers: dict | None = None) -> dict:
    return {
        "received_at": utc_now_iso(),
        "route": route,
        "symbol": payload.get("symbol") or payload.get("ticker"),
        "timeframe": payload.get("timeframe") or payload.get("tf"),
        "event": payload.get("event"),
        "setup": payload.get("setup"),
        "phase": payload.get("phase"),
        "strength": payload.get("strength"),
        "quality_score": payload.get("quality_score"),
        "price": payload.get("price"),
        "side": payload.get("side"),
        "payload": payload,
        "headers": headers or {},
       
    }


def validate_secret(x_webhook_secret: Optional[str]) -> None:
    expected_secret = os.getenv("WEBHOOK_SECRET")

    if expected_secret and x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized webhook secret")


@app.get("/")
async def healthcheck():
    return {
        "ok": True,
        "service": "tradingview-webhook",
        "timestamp": utc_now_iso(),
        "routes": ["/", "/api/webhook"],
    }


@app.post("/")
async def root_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(default=None)
):
    validate_secret(x_webhook_secret)

    raw_body = await request.body()
    payload = parse_payload(raw_body)

    log_data = build_log(
        route="/",
        payload=payload,
        headers={
            "content_type": request.headers.get("content-type", ""),
            "user_agent": request.headers.get("user-agent", ""),
        },
    )
    print(json.dumps(log_data, ensure_ascii=False))

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "message": "Alert received on root route",
            "received_at": utc_now_iso(),
            "route": "/",
            "payload": payload,
        },
    )


@app.post("/api/webhook")
async def tradingview_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(default=None)
):
    validate_secret(x_webhook_secret)

    raw_body = await request.body()
    payload = parse_payload(raw_body)

    log_data = build_log(
        route="/api/webhook",
        payload=payload,
        headers={
            "content_type": request.headers.get("content-type", ""),
            "user_agent": request.headers.get("user-agent", ""),
        },
    )
    print(json.dumps(log_data, ensure_ascii=False))

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "message": "Alert received",
            "received_at": utc_now_iso(),
            "route": "/api/webhook",
            "payload": payload,
        },
    )
