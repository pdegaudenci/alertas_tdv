import asyncio
import json
import logging
import traceback
import uuid
from typing import Any, Dict, List, Optional

from app.services.lambda_alert_processor_service import process_lambda_alert_payload
from app.services.webhook_background_service import process_alert_background
from app.services.sqs_fragment_store_service import (
    mark_fragment_processed,
    mark_fragment_error,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _log(level: str, payload: Dict[str, Any]) -> None:
    msg = json.dumps(payload, ensure_ascii=False, default=str)

    if level.upper() == "ERROR":
        logger.error(msg)
    elif level.upper() == "WARNING":
        logger.warning(msg)
    else:
        logger.info(msg)


def _safe_json_loads(raw_body: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw_body)

        if not isinstance(data, dict):
            raise ValueError("SQS body is not a JSON object")

        return data

    except Exception as exc:
        raise ValueError(f"Invalid SQS message body: {exc}") from exc


def _extract_trace_id(payload: Dict[str, Any], record: Dict[str, Any]) -> str:
    return (
        payload.get("trace_id")
        or payload.get("event_uid")
        or record.get("messageId")
        or str(uuid.uuid4())
    )


def _extract_event_uid(payload: Dict[str, Any]) -> Optional[str]:
    event_uid = payload.get("event_uid")

    if event_uid:
        return str(event_uid)

    signal = payload.get("signal")

    if isinstance(signal, dict) and signal.get("event_uid"):
        return str(signal.get("event_uid"))

    return None


def _extract_signal_field(payload: Dict[str, Any], field: str) -> Optional[Any]:
    signal = payload.get("signal")

    if isinstance(signal, dict):
        return signal.get(field)

    return None


async def _process_one_record(record: Dict[str, Any]) -> None:
    body = record.get("body") or ""
    raw_payload = _safe_json_loads(body)

    trace_id = _extract_trace_id(raw_payload, record)
    raw_message_type = raw_payload.get("message_type")
    raw_event_uid = _extract_event_uid(raw_payload)

    _log(
        "INFO",
        {
            "level": "INFO",
            "component": "lambda_sqs_consumer",
            "stage": "sqs_record_received",
            "trace_id": trace_id,
            "aws_message_id": record.get("messageId"),
            "message_type": raw_message_type,
            "event_uid": raw_event_uid,
            "event": _extract_signal_field(raw_payload, "event"),
            "side": _extract_signal_field(raw_payload, "side"),
            "symbol": _extract_signal_field(raw_payload, "symbol"),
            "tf": _extract_signal_field(raw_payload, "tf"),
        },
    )

    assembled_payload = await process_lambda_alert_payload(
        payload=raw_payload,
        trace_id=trace_id,
    )

    if assembled_payload is None:
        _log(
            "INFO",
            {
                "level": "INFO",
                "component": "lambda_sqs_consumer",
                "stage": "fragment_stored_waiting_pair",
                "trace_id": trace_id,
                "aws_message_id": record.get("messageId"),
                "message_type": raw_message_type,
                "event_uid": raw_event_uid,
            },
        )

        return

    assembled_message_type = assembled_payload.get("message_type")
    assembled_event_uid = _extract_event_uid(assembled_payload)

    _log(
        "INFO",
        {
            "level": "INFO",
            "component": "lambda_sqs_consumer",
            "stage": "payload_ready_for_background_processing",
            "trace_id": trace_id,
            "aws_message_id": record.get("messageId"),
            "raw_message_type": raw_message_type,
            "assembled_message_type": assembled_message_type,
            "event_uid": assembled_event_uid,
            "event": _extract_signal_field(assembled_payload, "event"),
            "side": _extract_signal_field(assembled_payload, "side"),
            "symbol": _extract_signal_field(assembled_payload, "symbol"),
            "tf": _extract_signal_field(assembled_payload, "tf"),
        },
    )

    result = await process_alert_background(
        payload=assembled_payload,
        trace_id=trace_id,
    )

    if isinstance(result, dict):
        ok = result.get("ok", True)
        critical_error = result.get("critical_error", False)

        if ok is False or critical_error is True:
            if assembled_event_uid:
                await mark_fragment_error(
                    event_uid=assembled_event_uid,
                    error=result,
                    trace_id=trace_id,
                )

            raise RuntimeError(
                json.dumps(
                    {
                        "message": "process_alert_background returned critical error",
                        "trace_id": trace_id,
                        "event_uid": assembled_event_uid,
                        "result": result,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )

    if assembled_event_uid and assembled_message_type == "logical_event_full":
        await mark_fragment_processed(
            event_uid=assembled_event_uid,
            merged_payload=assembled_payload,
            validation_payload=result or {},
            trace_id=trace_id,
        )

    _log(
        "INFO",
        {
            "level": "INFO",
            "component": "lambda_sqs_consumer",
            "stage": "sqs_record_processed_ok",
            "trace_id": trace_id,
            "aws_message_id": record.get("messageId"),
            "raw_message_type": raw_message_type,
            "processed_message_type": assembled_message_type,
            "event_uid": assembled_event_uid,
        },
    )


async def _process_batch(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    batch_item_failures: List[Dict[str, str]] = []

    for record in records:
        message_id = record.get("messageId")

        try:
            await _process_one_record(record)

        except Exception as exc:
            _log(
                "ERROR",
                {
                    "level": "ERROR",
                    "component": "lambda_sqs_consumer",
                    "stage": "sqs_record_processing_failed",
                    "aws_message_id": message_id,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )

            if message_id:
                batch_item_failures.append(
                    {
                        "itemIdentifier": message_id
                    }
                )

    return batch_item_failures


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, List[Dict[str, str]]]:
    records = event.get("Records", [])

    _log(
        "INFO",
        {
            "level": "INFO",
            "component": "lambda_sqs_consumer",
            "stage": "lambda_batch_start",
            "records_count": len(records),
            "aws_request_id": getattr(context, "aws_request_id", None),
        },
    )

    batch_item_failures = asyncio.run(_process_batch(records))

    _log(
        "INFO",
        {
            "level": "INFO",
            "component": "lambda_sqs_consumer",
            "stage": "lambda_batch_done",
            "records_count": len(records),
            "failed_count": len(batch_item_failures),
            "aws_request_id": getattr(context, "aws_request_id", None),
        },
    )

    return {
        "batchItemFailures": batch_item_failures
    }