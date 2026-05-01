"""
Servicio de cola de alertas TradingView.

Responsabilidad:
- Guardar rápidamente alertas recibidas por webhook.
- Evitar timeout en TradingView.
- Persistir logical_event_core / logical_event_extra como fragmentos.
- Ensamblar core + extra posteriormente desde Supabase.
- Exponer alertas PENDING para procesamiento pesado.
"""

from typing import Any, Dict, List, Optional
import time
import traceback
from app.core.logging import log_event, log_trace
from app.utils.json_utils import sanitize_for_json
from app.utils.math_utils import nested_get
from app.utils.time_utils import utc_now_iso

from app.services.alert_service import (
    ensure_canonical_schema,
    merge_core_extra_payloads,
)

from app.repositories.supabase_repo import (
    SUPABASE_RUNTIME_ENABLED,
    supabase,
)


QUEUE_TABLE = "backend_alert_queue"

SPLIT_MESSAGE_TYPES = {
    "logical_event_core",
    "logical_event_extra",
}

PROCESSABLE_STATUSES = {
    "PENDING",
}


def _extract_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}

    return {
        "event_uid": payload.get("event_uid"),
        "message_type": payload.get("message_type"),
        "schema_version": payload.get("schema_version"),
        "symbol": signal.get("symbol") or payload.get("symbol") or payload.get("ticker"),
        "timeframe": signal.get("tf") or payload.get("tf") or payload.get("timeframe"),
        "event": signal.get("event") or payload.get("event"),
        "side": signal.get("side") or payload.get("side"),
    }


def _is_split_payload(payload: Dict[str, Any]) -> bool:
    message_type = str(payload.get("message_type") or "").lower()
    return message_type in SPLIT_MESSAGE_TYPES


def _is_processable_immediately(payload: Dict[str, Any]) -> bool:
    message_type = str(payload.get("message_type") or "").lower()
    return message_type not in SPLIT_MESSAGE_TYPES


async def enqueue_alert_payload(
    payload: Dict[str, Any],
    trace_id: str,
    source: str = "tradingview_webhook",
) -> Dict[str, Any]:
    """
    Guarda un payload en la cola.

    - logical_event_core / logical_event_extra quedan como RECEIVED.
    - executed_event / logical_event_full / otros completos quedan como PENDING.
    """

    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        log_trace(trace_id, "alert_queue_enqueue_skipped", {
            "reason": "supabase_not_configured",
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
        }, level="ERROR")

        return {
            "ok": False,
            "queued": False,
            "reason": "supabase_not_configured",
        }

    try:
        canonical = ensure_canonical_schema(payload)
        summary = _extract_summary(canonical)

        status = "PENDING" if _is_processable_immediately(canonical) else "RECEIVED"

        row = sanitize_for_json({
            **summary,
            "trace_id": trace_id,
            "status": status,
            "payload": canonical,
            "source": source,
            "metadata": {
                "queued_at": utc_now_iso(),
                "is_split_payload": _is_split_payload(canonical),
                "source": source,
            },
        })

        event_uid = row.get("event_uid")
        message_type = row.get("message_type")

        if event_uid and message_type:
            resp = (
                supabase
                .table(QUEUE_TABLE)
                .upsert(
                    row,
                    on_conflict="event_uid,message_type",
                )
                .execute()
            )
        else:
            resp = (
                supabase
                .table(QUEUE_TABLE)
                .insert(row)
                .execute()
            )

        log_trace(trace_id, "alert_queue_enqueue_ok", {
            "event_uid": event_uid,
            "message_type": message_type,
            "status": status,
            "rows": len(resp.data or []),
        })

        return {
            "ok": True,
            "queued": True,
            "status": status,
            "event_uid": event_uid,
            "message_type": message_type,
        }

    except Exception as e:
        log_trace(trace_id, "alert_queue_enqueue_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
        }, level="ERROR")

        return {
            "ok": False,
            "queued": False,
            "error": str(e),
        }


async def assemble_pending_core_extra_pairs(
    limit: int = 100,
    trace_id: str = "-",
) -> Dict[str, Any]:
    """
    Busca logical_event_core + logical_event_extra con mismo event_uid
    y crea una fila logical_event_full en estado PENDING.

    Los fragmentos se marcan como ASSEMBLED.
    """

    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return {
            "ok": False,
            "assembled": 0,
            "reason": "supabase_not_configured",
        }

    try:
        resp = (
            supabase
            .table(QUEUE_TABLE)
            .select("*")
            .eq("status", "RECEIVED")
            .in_("message_type", ["logical_event_core", "logical_event_extra"])
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )

        rows = resp.data or []

        grouped: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            event_uid = row.get("event_uid")
            message_type = row.get("message_type")

            if not event_uid or not message_type:
                continue

            if event_uid not in grouped:
                grouped[event_uid] = {}

            grouped[event_uid][message_type] = row

        assembled_count = 0
        assembled_event_uids: List[str] = []

        for event_uid, parts in grouped.items():
            core_row = parts.get("logical_event_core")
            extra_row = parts.get("logical_event_extra")

            if not core_row or not extra_row:
                continue

            core_payload = core_row.get("payload") or {}
            extra_payload = extra_row.get("payload") or {}

            merged_payload = merge_core_extra_payloads(core_payload, extra_payload)
            merged_payload = ensure_canonical_schema(merged_payload)

            summary = _extract_summary(merged_payload)

            full_row = sanitize_for_json({
                **summary,
                "trace_id": trace_id,
                "status": "PENDING",
                "payload": merged_payload,
                "source": "queue_assembler",
                "metadata": {
                    "assembled_at": utc_now_iso(),
                    "assembled_from": [
                        core_row.get("id"),
                        extra_row.get("id"),
                    ],
                    "core_created_at": core_row.get("created_at"),
                    "extra_created_at": extra_row.get("created_at"),
                },
            })

            (
                supabase
                .table(QUEUE_TABLE)
                .upsert(
                    full_row,
                    on_conflict="event_uid,message_type",
                )
                .execute()
            )

            (
                supabase
                .table(QUEUE_TABLE)
                .update({
                    "status": "ASSEMBLED",
                    "processed_at": utc_now_iso(),
                })
                .in_("id", [core_row.get("id"), extra_row.get("id")])
                .execute()
            )

            assembled_count += 1
            assembled_event_uids.append(event_uid)

        log_trace(trace_id, "alert_queue_assemble_done", {
            "assembled": assembled_count,
            "event_uids": assembled_event_uids[:20],
        })

        return {
            "ok": True,
            "assembled": assembled_count,
            "event_uids": assembled_event_uids,
        }

    except Exception as e:
        log_trace(trace_id, "alert_queue_assemble_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")

        return {
            "ok": False,
            "assembled": 0,
            "error": str(e),
        }


async def get_pending_alerts_for_processing(
    limit: int = 5,
    trace_id: str = "-",
) -> List[Dict[str, Any]]:
    """
    Devuelve alertas completas pendientes de procesar.

    No devuelve logical_event_core / logical_event_extra sueltos.
    """

    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return []

    limit = max(1, min(int(limit), 25))

    try:
        resp = (
            supabase
            .table(QUEUE_TABLE)
            .select("*")
            .eq("status", "PENDING")
            .not_.in_("message_type", ["logical_event_core", "logical_event_extra"])
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )

        rows = resp.data or []

        log_trace(trace_id, "alert_queue_pending_read_ok", {
            "count": len(rows),
            "limit": limit,
        })

        return rows

    except Exception as e:
        log_trace(trace_id, "alert_queue_pending_read_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")
        return []


async def mark_queue_item_processing(
    queue_id: str,
    trace_id: str,
) -> None:
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return

    try:
        (
            supabase
            .table(QUEUE_TABLE)
            .update({
                "status": "PROCESSING",
                "locked_at": utc_now_iso(),
                "trace_id": trace_id,
            })
            .eq("id", queue_id)
            .execute()
        )
    except Exception as e:
        log_trace(trace_id, "alert_queue_mark_processing_error", {
            "queue_id": queue_id,
            "error": str(e),
        }, level="ERROR")


async def mark_queue_item_processed(
    queue_id: str,
    validation_payload: Optional[Dict[str, Any]],
    trace_id: str,
) -> None:
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return

    try:
        (
            supabase
            .table(QUEUE_TABLE)
            .update(sanitize_for_json({
                "status": "PROCESSED",
                "processed_at": utc_now_iso(),
                "validation_payload": validation_payload or {},
                "last_error": None,
                "last_error_at": None,
            }))
            .eq("id", queue_id)
            .execute()
        )
    except Exception as e:
        log_trace(trace_id, "alert_queue_mark_processed_error", {
            "queue_id": queue_id,
            "error": str(e),
        }, level="ERROR")


async def mark_queue_item_error(
    queue_id: str,
    error: Exception | str,
    trace_id: str,
) -> None:
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return

    try:
        current = (
            supabase
            .table(QUEUE_TABLE)
            .select("attempts")
            .eq("id", queue_id)
            .limit(1)
            .execute()
        )

        rows = current.data or []
        attempts = int(rows[0].get("attempts") or 0) if rows else 0

        (
            supabase
            .table(QUEUE_TABLE)
            .update({
                "status": "ERROR",
                "attempts": attempts + 1,
                "last_error": str(error),
                "last_error_at": utc_now_iso(),
            })
            .eq("id", queue_id)
            .execute()
        )

    except Exception as e:
        log_trace(trace_id, "alert_queue_mark_error_failed", {
            "queue_id": queue_id,
            "original_error": str(error),
            "update_error": str(e),
        }, level="ERROR")


async def get_queue_status(trace_id: str = "-") -> Dict[str, Any]:
    """
    Devuelve conteos por status para debug.
    """

    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return {
            "ok": False,
            "message": "Supabase not configured",
            "items": [],
        }

    try:
        resp = (
            supabase
            .table(QUEUE_TABLE)
            .select("status")
            .execute()
        )

        rows = resp.data or []

        counts: Dict[str, int] = {}

        for row in rows:
            status = row.get("status") or "UNKNOWN"
            counts[status] = counts.get(status, 0) + 1

        return {
            "ok": True,
            "counts": counts,
            "total": len(rows),
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }