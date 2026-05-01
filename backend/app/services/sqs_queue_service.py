"""
Servicio AWS SQS para cola de alertas TradingView.

Responsabilidad:
- Enviar payloads del webhook a SQS rápidamente.
- Leer mensajes pendientes desde SQS.
- Borrar mensajes procesados correctamente.
- Cambiar visibilidad en caso necesario.
- No reemplaza Supabase operativo.
"""

from typing import Any, Dict, List, Optional
import json
import os
import traceback

import boto3

from app.core.logging import log_trace, log_event
from app.utils.time_utils import utc_now_iso
from app.utils.json_utils import sanitize_for_json


AWS_REGION = os.getenv("AWS_REGION", "eu-west-1").strip()

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "").strip()

SQS_MAX_MESSAGES = int(os.getenv("SQS_MAX_MESSAGES", "10"))
SQS_WAIT_TIME_SECONDS = int(os.getenv("SQS_WAIT_TIME_SECONDS", "5"))
SQS_VISIBILITY_TIMEOUT = int(os.getenv("SQS_VISIBILITY_TIMEOUT", "120"))

_sqs_client = None


def get_sqs_client():
    global _sqs_client

    if _sqs_client is not None:
        return _sqs_client

    _sqs_client = boto3.client(
        "sqs",
        region_name=AWS_REGION or None,
    )

    log_event("sqs_client_init_ok", {
        "region": AWS_REGION,
        "queue_url_configured": bool(SQS_QUEUE_URL),
    })

    return _sqs_client


def is_sqs_configured() -> bool:
    return bool(SQS_QUEUE_URL)


def build_sqs_message_body(
    payload: Dict[str, Any],
    trace_id: str,
    source: str = "tradingview_webhook",
) -> Dict[str, Any]:
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}

    return sanitize_for_json({
        "trace_id": trace_id,
        "source": source,
        "queued_at": utc_now_iso(),

        "event_uid": payload.get("event_uid"),
        "schema_version": payload.get("schema_version"),
        "message_type": payload.get("message_type"),

        "symbol": signal.get("symbol") or payload.get("symbol") or payload.get("ticker"),
        "timeframe": signal.get("tf") or payload.get("tf") or payload.get("timeframe"),
        "event": signal.get("event") or payload.get("event"),
        "side": signal.get("side") or payload.get("side"),

        "payload": payload,
    })


async def send_alert_to_sqs(
    payload: Dict[str, Any],
    trace_id: str,
    source: str = "tradingview_webhook",
) -> Dict[str, Any]:
    """
    Envía una alerta a SQS.

    Debe ser rápido para que TradingView no haga timeout.
    """

    if not is_sqs_configured():
        log_trace(trace_id, "sqs_send_skipped", {
            "reason": "SQS_QUEUE_URL_not_configured",
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
        }, level="ERROR")

        return {
            "ok": False,
            "queued": False,
            "reason": "SQS_QUEUE_URL_not_configured",
        }

    try:
        sqs = get_sqs_client()

        body = build_sqs_message_body(
            payload=payload,
            trace_id=trace_id,
            source=source,
        )

        response = sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(body, ensure_ascii=False, default=str),
            MessageAttributes={
                "message_type": {
                    "DataType": "String",
                    "StringValue": str(payload.get("message_type") or "unknown"),
                },
                "event_uid": {
                    "DataType": "String",
                    "StringValue": str(payload.get("event_uid") or "unknown"),
                },
                "source": {
                    "DataType": "String",
                    "StringValue": source,
                },
            },
        )

        message_id = response.get("MessageId")

        log_trace(trace_id, "sqs_send_ok", {
            "message_id": message_id,
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
        })

        return {
            "ok": True,
            "queued": True,
            "message_id": message_id,
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
        }

    except Exception as e:
        log_trace(trace_id, "sqs_send_error", {
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


async def receive_sqs_messages(
    trace_id: str,
    max_messages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Lee mensajes de SQS.

    No borra mensajes. El caller debe borrar solo si el procesamiento fue correcto.
    """

    if not is_sqs_configured():
        log_trace(trace_id, "sqs_receive_skipped", {
            "reason": "SQS_QUEUE_URL_not_configured",
        }, level="ERROR")
        return []

    try:
        sqs = get_sqs_client()

        max_messages = max_messages or SQS_MAX_MESSAGES
        max_messages = max(1, min(int(max_messages), 10))

        response = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=SQS_WAIT_TIME_SECONDS,
            VisibilityTimeout=SQS_VISIBILITY_TIMEOUT,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
        )

        messages = response.get("Messages", []) or []

        parsed_messages = []

        for message in messages:
            body_raw = message.get("Body") or "{}"

            try:
                body = json.loads(body_raw)
            except Exception:
                body = {
                    "raw_body": body_raw,
                    "payload": {},
                }

            parsed_messages.append({
                "message_id": message.get("MessageId"),
                "receipt_handle": message.get("ReceiptHandle"),
                "attributes": message.get("Attributes", {}),
                "message_attributes": message.get("MessageAttributes", {}),
                "body": body,
                "payload": body.get("payload") if isinstance(body, dict) else {},
            })

        log_trace(trace_id, "sqs_receive_ok", {
            "count": len(parsed_messages),
            "max_messages": max_messages,
        })

        return parsed_messages

    except Exception as e:
        log_trace(trace_id, "sqs_receive_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")
        return []


async def delete_sqs_message(
    receipt_handle: str,
    trace_id: str,
) -> bool:
    if not receipt_handle:
        return False

    if not is_sqs_configured():
        return False

    try:
        sqs = get_sqs_client()

        sqs.delete_message(
            QueueUrl=SQS_QUEUE_URL,
            ReceiptHandle=receipt_handle,
        )

        log_trace(trace_id, "sqs_delete_ok", {
            "receipt_handle_present": bool(receipt_handle),
        })

        return True

    except Exception as e:
        log_trace(trace_id, "sqs_delete_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")
        return False


async def change_sqs_message_visibility(
    receipt_handle: str,
    visibility_timeout: int,
    trace_id: str,
) -> bool:
    if not receipt_handle:
        return False

    if not is_sqs_configured():
        return False

    try:
        sqs = get_sqs_client()

        sqs.change_message_visibility(
            QueueUrl=SQS_QUEUE_URL,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=int(visibility_timeout),
        )

        log_trace(trace_id, "sqs_change_visibility_ok", {
            "visibility_timeout": visibility_timeout,
        })

        return True

    except Exception as e:
        log_trace(trace_id, "sqs_change_visibility_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")
        return False


async def get_sqs_queue_status(trace_id: str = "-") -> Dict[str, Any]:
    if not is_sqs_configured():
        return {
            "ok": False,
            "message": "SQS_QUEUE_URL not configured",
        }

    try:
        sqs = get_sqs_client()

        response = sqs.get_queue_attributes(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
                "CreatedTimestamp",
                "LastModifiedTimestamp",
                "VisibilityTimeout",
                "MaximumMessageSize",
                "MessageRetentionPeriod",
                "RedrivePolicy",
            ],
        )

        attrs = response.get("Attributes", {})

        return {
            "ok": True,
            "queue_url_configured": bool(SQS_QUEUE_URL),
            "attributes": attrs,
        }

    except Exception as e:
        log_trace(trace_id, "sqs_status_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")

        return {
            "ok": False,
            "error": str(e),
        }