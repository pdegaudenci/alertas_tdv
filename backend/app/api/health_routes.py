"""
Rutas de healthcheck del backend.

Endpoints:
- /
- /api/health/binance
- /api/health/supabase
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import BINANCE_BASE_URLS, SKLEARN_MODEL, ALLOWED_ORIGINS
from app.utils.time_utils import utc_now_iso
from app.services.binance_service import fetch_depth

from app.repositories.supabase_repo import (
    SUPABASE_RUNTIME_ENABLED,
    supabase,
)


router = APIRouter()


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
        "model_loaded": SKLEARN_MODEL is not None,
        "allowed_origins": ALLOWED_ORIGINS,
    }


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
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
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