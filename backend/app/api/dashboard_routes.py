"""
Rutas de consulta para dashboard.

Endpoints:
- /api/latest
- /api/validation/latest
- /api/alerts
- /api/alerts/supabase
- /api/setups/supabase
"""

from fastapi import APIRouter

from app.core.state import LAST_ALERT, LAST_VALIDATION, ALERT_HISTORY

from app.repositories.supabase_repo import (
    get_alerts_supabase_service,
    get_setups_supabase_service,
)


router = APIRouter()


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


@router.get("/api/alerts/supabase")
async def get_alerts_supabase(limit: int = 50):
    return await get_alerts_supabase_service(limit)


@router.get("/api/setups/supabase")
async def get_setups_supabase(limit: int = 50):
    return await get_setups_supabase_service(limit)