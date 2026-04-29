"""
Seguridad del webhook.

Contiene la validación del header x-webhook-secret 
"""

from typing import Optional
from fastapi import HTTPException

from app.core.config import WEBHOOK_SECRET_ENV


def validate_secret(x_webhook_secret: Optional[str]) -> None:
    if WEBHOOK_SECRET_ENV and x_webhook_secret != WEBHOOK_SECRET_ENV:
        raise HTTPException(status_code=401, detail="Unauthorized webhook secret")