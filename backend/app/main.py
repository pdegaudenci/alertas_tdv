"""
Entrada principal de FastAPI.

Este archivo crea la app FastAPI y configura CORS. 
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import (
    ALLOWED_ORIGINS,
    BINANCE_BASE_URLS,
    SKLEARN_MODEL,
)
from app.utils.time_utils import utc_now_iso

app = FastAPI(
    title="TradingView Validation Layer",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
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
        "model_loaded": SKLEARN_MODEL is not None,
        "allowed_origins": ALLOWED_ORIGINS,
    }