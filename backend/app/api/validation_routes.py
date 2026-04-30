"""
Rutas de validación manual.

Endpoints:
- /api/validate
"""

from typing import Optional

from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import JSONResponse

from app.core.state import LAST_ALERT
from app.core.security import validate_secret
from app.core.logging import log_event

from app.utils.json_utils import sanitize_for_json

from app.services.alert_service import parse_payload
from app.services.validation_service import run_validation


router = APIRouter()


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