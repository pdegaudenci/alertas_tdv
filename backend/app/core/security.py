"""
Seguridad del webhook.

Permite validar el secreto desde:
- Header x-webhook-secret
- Campo secret dentro del payload JSON de TradingView

TradingView no permite enviar headers personalizados en alertas,
por eso es necesario aceptar payload.secret.
"""

import hmac
from typing import Optional

from fastapi import HTTPException

from app.core.config import WEBHOOK_SECRET_ENV


def validate_secret(
    x_webhook_secret: Optional[str] = None,
    payload_secret: Optional[str] = None,
) -> None:
    """
    Valida el secreto del webhook.

    Orden:
    1. Header x-webhook-secret
    2. payload.secret

    Si WEBHOOK_SECRET no está configurado, no bloquea.
    """

    expected_secret = (WEBHOOK_SECRET_ENV or "").strip()

    if not expected_secret:
        return

    received_secret = (
        (x_webhook_secret or "").strip()
        or
        (payload_secret or "").strip()
    )

    if not received_secret:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: missing webhook secret",
        )

    if not hmac.compare_digest(received_secret, expected_secret):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: invalid webhook secret",
        )