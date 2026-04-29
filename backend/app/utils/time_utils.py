"""
Contiene funciones relacionadas con timestamps UTC usadas por logging,
persistencia, respuestas API y trazabilidad.
"""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()