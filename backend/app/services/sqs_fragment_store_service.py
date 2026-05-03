"""
Servicio de buffer para fragmentos SQS CORE/EXTRA.

Objetivo:
- SQS sigue siendo la cola real.
- Supabase solo guarda temporalmente logical_event_core y logical_event_extra.
- Cuando ambos fragmentos existen, se arma logical_event_full.
- Evita depender de que CORE y EXTRA lleguen en el mismo receive_message().
"""

from typing import Any, Dict, Optional
import traceback

from app.repositories.supabase_repo import SUPABASE_RUNTIME_ENABLED, supabase
from app.core.logging import log_trace
from app.utils.time_utils import utc_now_iso
from app.utils.json_utils import sanitize_for_json


TABLE_NAME = "sqs_alert_fragments"


def _message_type(payload: Dict[str, Any]) -> str:
    return str(payload.get("message_type") or "").lower().strip()


def _event_uid(payload: Dict[str, Any]) -> str:
    return str(payload.get("event_uid") or "").strip()


async def get_fragment_row(event_uid: str, trace_id: str = "-") -> Optional[Dict[str, Any]]:
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return None

    try:
        resp = (
            supabase
            .table(TABLE_NAME)
            .select("*")
            .eq("event_uid", event_uid)
            .limit(1)
            .execute()
        )

        rows = resp.data or []

        if not rows:
            return None

        return rows[0]

    except Exception as e:
        log_trace(trace_id, "sqs_fragment_get_error", {
            "event_uid": event_uid,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")
        return None


async def upsert_fragment_payload(
    payload: Dict[str, Any],
    trace_id: str,
) -> Dict[str, Any]:
    """
    Guarda CORE o EXTRA en la tabla buffer.

    Devuelve:
    {
        ok,
        complete,
        row,
        event_uid
    }
    """

    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return {
            "ok": False,
            "complete": False,
            "reason": "supabase_not_configured",
        }

    event_uid = _event_uid(payload)
    message_type = _message_type(payload)

    if not event_uid:
        return {
            "ok": False,
            "complete": False,
            "reason": "missing_event_uid",
        }

    if message_type not in {"logical_event_core", "logical_event_extra"}:
        return {
            "ok": False,
            "complete": False,
            "reason": f"unsupported_message_type:{message_type}",
        }

    try:
        existing = await get_fragment_row(event_uid, trace_id=trace_id)

        now = utc_now_iso()

        if existing:
            update_data = {
                "trace_id": trace_id,
                "metadata": sanitize_for_json({
                    **(existing.get("metadata") or {}),
                    "last_fragment_received_at": now,
                    "last_message_type": message_type,
                }),
            }

            if message_type == "logical_event_core":
                update_data["core_payload"] = sanitize_for_json(payload)
                update_data["core_received_at"] = now

            if message_type == "logical_event_extra":
                update_data["extra_payload"] = sanitize_for_json(payload)
                update_data["extra_received_at"] = now

            core_payload = update_data.get("core_payload") or existing.get("core_payload")
            extra_payload = update_data.get("extra_payload") or existing.get("extra_payload")

            update_data["status"] = "READY" if core_payload and extra_payload else "WAITING_PAIR"

            resp = (
                supabase
                .table(TABLE_NAME)
                .update(sanitize_for_json(update_data))
                .eq("event_uid", event_uid)
                .execute()
            )

        else:
            row = {
                "event_uid": event_uid,
                "trace_id": trace_id,
                "status": "WAITING_PAIR",
                "metadata": {
                    "created_from": "sqs_processor",
                    "first_message_type": message_type,
                    "first_fragment_received_at": now,
                },
            }

            if message_type == "logical_event_core":
                row["core_payload"] = sanitize_for_json(payload)
                row["core_received_at"] = now

            if message_type == "logical_event_extra":
                row["extra_payload"] = sanitize_for_json(payload)
                row["extra_received_at"] = now

            resp = (
                supabase
                .table(TABLE_NAME)
                .upsert(
                    sanitize_for_json(row),
                    on_conflict="event_uid",
                )
                .execute()
            )

        updated = await get_fragment_row(event_uid, trace_id=trace_id)

        complete = bool(
            updated
            and updated.get("core_payload")
            and updated.get("extra_payload")
        )

        if complete and updated.get("status") != "READY":
            (
                supabase
                .table(TABLE_NAME)
                .update({"status": "READY"})
                .eq("event_uid", event_uid)
                .execute()
            )
            updated = await get_fragment_row(event_uid, trace_id=trace_id)

        core_debug = updated.get("core_payload") if isinstance(updated, dict) else None
        extra_debug = updated.get("extra_payload") if isinstance(updated, dict) else None

        core_signal = core_debug.get("signal", {}) if isinstance(core_debug, dict) and isinstance(core_debug.get("signal"), dict) else {}
        core_trade_plan = core_debug.get("trade_plan", {}) if isinstance(core_debug, dict) and isinstance(core_debug.get("trade_plan"), dict) else {}

        extra_signal = extra_debug.get("signal", {}) if isinstance(extra_debug, dict) and isinstance(extra_debug.get("signal"), dict) else {}

        log_trace(trace_id, "sqs_fragment_upsert_ok", {
            "event_uid": event_uid,
            "message_type": message_type,
            "complete": complete,
            "status": updated.get("status") if updated else None,
            "core_message_type": core_debug.get("message_type") if isinstance(core_debug, dict) else None,
            "core_event": core_signal.get("event"),
            "core_side": core_signal.get("side"),
            "core_price": core_signal.get("price"),
            "core_entry_price": core_signal.get("entry_price"),
            "core_tp_price": core_trade_plan.get("tp_price"),
            "core_sl_price": core_trade_plan.get("sl_price"),
            "extra_message_type": extra_debug.get("message_type") if isinstance(extra_debug, dict) else None,
            "extra_has_signal": bool(extra_signal),
        })

        return {
            "ok": True,
            "complete": complete,
            "row": updated,
            "event_uid": event_uid,
        }

    except Exception as e:
        log_trace(trace_id, "sqs_fragment_upsert_error", {
            "event_uid": event_uid,
            "message_type": message_type,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")

        return {
            "ok": False,
            "complete": False,
            "event_uid": event_uid,
            "error": str(e),
        }


async def mark_fragment_processed(
    event_uid: str,
    merged_payload: Dict[str, Any],
    validation_payload: Dict[str, Any],
    trace_id: str,
) -> None:
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return

    try:
        (
            supabase
            .table(TABLE_NAME)
            .update(sanitize_for_json({
                "status": "PROCESSED",
                "processed_at": utc_now_iso(),
                "merged_payload": merged_payload,
                "validation_payload": validation_payload,
                "last_error": None,
                "last_error_at": None,
                "trace_id": trace_id,
            }))
            .eq("event_uid", event_uid)
            .execute()
        )

        log_trace(trace_id, "sqs_fragment_mark_processed_ok", {
            "event_uid": event_uid,
        })

    except Exception as e:
        log_trace(trace_id, "sqs_fragment_mark_processed_error", {
            "event_uid": event_uid,
            "error": str(e),
        }, level="ERROR")


async def mark_fragment_error(
    event_uid: str,
    error: Exception | str,
    trace_id: str,
) -> None:
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return

    try:
        existing = await get_fragment_row(event_uid, trace_id=trace_id)
        attempts = int(existing.get("attempts") or 0) if existing else 0

        (
            supabase
            .table(TABLE_NAME)
            .update({
                "status": "ERROR",
                "attempts": attempts + 1,
                "last_error": str(error),
                "last_error_at": utc_now_iso(),
                "trace_id": trace_id,
            })
            .eq("event_uid", event_uid)
            .execute()
        )

        log_trace(trace_id, "sqs_fragment_mark_error_ok", {
            "event_uid": event_uid,
            "error": str(error),
        })

    except Exception as e:
        log_trace(trace_id, "sqs_fragment_mark_error_failed", {
            "event_uid": event_uid,
            "original_error": str(error),
            "error": str(e),
        }, level="ERROR")