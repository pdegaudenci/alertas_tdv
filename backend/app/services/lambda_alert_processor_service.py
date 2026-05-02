"""
Servicio de preparación de payloads para AWS Lambda + SQS.

Responsabilidad:
- Recibir mensajes desde SQS.
- Si llega logical_event_core o logical_event_extra:
    - guardarlo en Supabase sqs_alert_fragments
    - esperar hasta tener ambos fragmentos
    - fusionar CORE + EXTRA en logical_event_full
- Si llega logical_event_full o executed_event:
    - devolverlo directamente
- No ejecuta validación.
- La validación sigue en process_alert_background().
"""

from typing import Any, Dict, Optional
import copy

from app.core.logging import log_trace
from app.utils.json_utils import sanitize_for_json
from app.utils.time_utils import utc_now_iso

from app.services.sqs_fragment_store_service import (
    upsert_fragment_payload,
    mark_fragment_error,
)


CORE_TYPE = "logical_event_core"
EXTRA_TYPE = "logical_event_extra"
FULL_TYPE = "logical_event_full"
EXECUTED_TYPE = "executed_event"


def _get_message_type(payload: Dict[str, Any]) -> str:
    return str(payload.get("message_type") or "").lower().strip()


def _get_event_uid(payload: Dict[str, Any]) -> Optional[str]:
    event_uid = payload.get("event_uid")

    if event_uid:
        return str(event_uid).strip()

    signal = payload.get("signal") or {}
    signal_event_uid = signal.get("event_uid")

    if signal_event_uid:
        return str(signal_event_uid).strip()

    return None


def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)

    for key, value in extra.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)

    return result


def _build_logical_event_full(
    core_payload: Dict[str, Any],
    extra_payload: Dict[str, Any],
    trace_id: str,
) -> Dict[str, Any]:
    merged = _deep_merge(core_payload, extra_payload)

    merged["message_type"] = FULL_TYPE
    merged["assembled_from"] = [CORE_TYPE, EXTRA_TYPE]
    merged["assembled_at"] = utc_now_iso()
    merged["trace_id"] = trace_id

    if not merged.get("schema_version"):
        merged["schema_version"] = "2.0"

    return sanitize_for_json(merged)


async def process_lambda_alert_payload(
    payload: Dict[str, Any],
    trace_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Devuelve:
    - payload completo si debe procesarse
    - None si solo se guardó fragmento y falta CORE o EXTRA
    """

    message_type = _get_message_type(payload)
    event_uid = _get_event_uid(payload)

    log_trace(trace_id, "lambda_payload_received", {
        "message_type": message_type,
        "event_uid": event_uid,
    })

    if message_type in {FULL_TYPE, EXECUTED_TYPE}:
        payload["trace_id"] = trace_id
        return sanitize_for_json(payload)

    if message_type not in {CORE_TYPE, EXTRA_TYPE}:
        payload["trace_id"] = trace_id
        return sanitize_for_json(payload)

    if not event_uid:
        raise ValueError("Fragment payload missing event_uid")

    upsert_result = await upsert_fragment_payload(
        payload=payload,
        trace_id=trace_id,
    )

    if not upsert_result.get("ok"):
        await mark_fragment_error(
            event_uid=event_uid,
            error=upsert_result.get("error") or upsert_result.get("reason") or "fragment_upsert_failed",
            trace_id=trace_id,
        )

        raise RuntimeError({
            "stage": "fragment_upsert_failed",
            "event_uid": event_uid,
            "result": upsert_result,
        })

    if not upsert_result.get("complete"):
        log_trace(trace_id, "lambda_fragment_waiting_pair", {
            "event_uid": event_uid,
            "message_type": message_type,
        })

        return None

    row = upsert_result.get("row") or {}

    core_payload = row.get("core_payload")
    extra_payload = row.get("extra_payload")

    if not core_payload or not extra_payload:
        log_trace(trace_id, "lambda_fragment_marked_complete_but_missing_payload", {
            "event_uid": event_uid,
            "has_core": core_payload is not None,
            "has_extra": extra_payload is not None,
        }, level="ERROR")

        raise RuntimeError({
            "stage": "fragment_complete_but_missing_payload",
            "event_uid": event_uid,
        })

    assembled_payload = _build_logical_event_full(
        core_payload=core_payload,
        extra_payload=extra_payload,
        trace_id=trace_id,
    )

    log_trace(trace_id, "lambda_fragments_assembled", {
        "event_uid": event_uid,
        "message_type": FULL_TYPE,
    })

    return assembled_payload