"""
Estado global en memoria del backend.

Este archivo mantiene las  variables globales
LAST_ALERT, LAST_VALIDATION, ALERT_HISTORY y ASSEMBLED_EVENTS.
Centraliza el estado compartido para que rutas
y servicios puedan importarlo.
"""

from collections import deque
from typing import Dict, Any

LAST_ALERT = {
    "ok": False,
    "message": "No alerts received yet",
}

LAST_VALIDATION = {
    "ok": False,
    "message": "No validations yet",
}

ALERT_HISTORY = deque(maxlen=200)

ASSEMBLED_EVENTS: Dict[str, Dict[str, Any]] = {}