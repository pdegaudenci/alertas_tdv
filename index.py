from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import os
import json
from datetime import datetime, timezone

app = FastAPI(title="TradingView Webhook Receiver")


def parse_payload(raw_body: bytes, content_type: str | None):
    """
    Intenta parsear el body como JSON.
    Si no puede, lo devuelve como texto plano.
    """
    text_body = raw_body.decode("utf-8", errors="replace").strip()

    if not text_body:
        return {}

    # Intento 1: si viene como JSON válido
    try:
        return json.loads(text_body)
    except json.JSONDecodeError:
        pass

    # Intento 2: si TradingView lo manda como texto
    return {"raw_message": text_body}


@app.get("/")
async def healthcheck():
    return {
        "ok": True,
        "service": "tradingview-webhook",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/webhook")
async def tradingview_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(default=None)
):
    """
    Endpoint para recibir alertas de TradingView.
    Puedes protegerlo con un secreto opcional enviado en el header:
    X-Webhook-Secret
    """
    expected_secret = os.getenv("WEBHOOK_SECRET")

    if expected_secret:
        if x_webhook_secret != expected_secret:
            raise HTTPException(status_code=401, detail="Unauthorized webhook secret")

    raw_body = await request.body()
    content_type = request.headers.get("content-type", "")

    payload = parse_payload(raw_body, content_type)

    # Campos típicos que puedes enviar desde TradingView
    symbol = payload.get("symbol")
    timeframe = payload.get("timeframe")
    event = payload.get("event")
    setup = payload.get("setup")
    phase = payload.get("phase")
    strength = payload.get("strength")
    quality_score = payload.get("quality_score")
    price = payload.get("price")
    side = payload.get("side")

    # Log simple para revisar en Vercel Logs
    print(
        json.dumps(
            {
                "received_at": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "timeframe": timeframe,
                "event": event,
                "setup": setup,
                "phase": phase,
                "strength": strength,
                "quality_score": quality_score,
                "price": price,
                "side": side,
                "payload": payload,
            },
            ensure_ascii=False,
        )
    )

    # Aquí luego puedes:
    # - guardar en BD
    # - reenviar a tu backend real
    # - disparar ejecución en Binance
    # - notificar a tu panel Streamlit

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "message": "Alert received",
            "received_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        },
    )
