"""
Servicio de actualización de estado del webhook.

Responsabilidad:
- Preparar LAST_VALIDATION con estado queued.
- Preparar LAST_ALERT con resumen rápido.
- Preparar LAST_ALERT para payload parcial core/extra.

No cambia lógica de negocio.
Solo mueve construcción de diccionarios fuera de webhook_routes.py.
"""

from typing import Any, Dict

from app.core.state import LAST_ALERT, LAST_VALIDATION
from app.utils.time_utils import utc_now_iso
from app.utils.json_utils import sanitize_for_json


def extract_payload_blocks(payload: Dict[str, Any]) -> tuple[dict, dict, dict, dict]:
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    quality = payload.get("quality", {}) if isinstance(payload.get("quality"), dict) else {}
    htf_context = payload.get("htf_context", {}) if isinstance(payload.get("htf_context"), dict) else {}

    return signal, context, quality, htf_context


def set_validation_queued(payload: Dict[str, Any]) -> None:
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}

    LAST_VALIDATION.clear()
    LAST_VALIDATION.update(sanitize_for_json({
        "ok": True,
        "validated_at": utc_now_iso(),
        "message": "Validation queued in background",
        "validation": {
            "approve": False,
            "confidence": 0,
            "probability_tp_before_sl": None,
            "score_external": None,
            "reason": ["validation_queued_background"],
            "penalties": [],
            "event_type": signal.get("event") or payload.get("event"),
        },
    }))


def set_last_alert_fast_ack(payload: Dict[str, Any], trace_id: str) -> None:
    signal, context, quality, htf_context = extract_payload_blocks(payload)

    LAST_ALERT.clear()
    LAST_ALERT.update(sanitize_for_json({
        "ok": True,
        "received_at": utc_now_iso(),
        "route": "/api/webhook",
        "processing_mode": "fast_ack_background",
        "trace_id": trace_id,
        "schema_version": payload.get("schema_version"),
        "message_type": payload.get("message_type"),
        "event_uid": payload.get("event_uid"),
        "symbol": signal.get("symbol") or payload.get("symbol") or payload.get("ticker"),
        "timeframe": signal.get("tf") or payload.get("timeframe") or payload.get("tf"),
        "event": signal.get("event") or payload.get("event"),
        "setup": signal.get("setup") or payload.get("setup"),
        "phase": context.get("phase"),
        "regime": context.get("regime"),
        "strength": context.get("phase_strength") or payload.get("strength"),
        "phase_5m": htf_context.get("htf_phase") or payload.get("phase_5m"),
        "strength_5m": htf_context.get("htf_phase_strength") or payload.get("strength_5m"),
        "quality_score": quality.get("quality_score") or payload.get("quality_score") or payload.get("score"),
        "price": signal.get("price") or payload.get("price"),
        "side": signal.get("side") or payload.get("side"),
        "payload": payload,
        "validation": LAST_VALIDATION,
    }))


def set_last_alert_partial(payload: Dict[str, Any]) -> None:
    LAST_ALERT.clear()
    LAST_ALERT.update(sanitize_for_json({
        "ok": True,
        "received_at": utc_now_iso(),
        "message": "Partial payload received, waiting for CORE/EXTRA pair",
        "event_uid": payload.get("event_uid"),
        "message_type": payload.get("message_type"),
        "waiting_for_pair": True,
        "payload": payload,
    }))