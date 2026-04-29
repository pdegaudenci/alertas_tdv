"""
Logging JSON para Vercel.

Este archivo conserva la lógica  de logs compactos en JSON, trace_id,
máscara de secretos y sanitización de payloads antes de escribir logs.
"""

from typing import Any, Dict
import json
import time
import logging

from app.utils.time_utils import utc_now_iso
from app.utils.json_utils import sanitize_for_json

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("validation-layer")


def mask_secret_value(value: Any) -> Any:
    if value is None:
        return None

    text = str(value)

    if len(text) <= 8:
        return "***"

    return f"{text[:4]}...{text[-4:]}"


def safe_payload_for_log(payload: Dict[str, Any]) -> Dict[str, Any]:
    clean = sanitize_for_json(payload)

    if isinstance(clean, dict):
        if "secret" in clean:
            clean["secret"] = "***MASKED***"

        headers = clean.get("headers")

        if isinstance(headers, dict):
            for k in list(headers.keys()):
                if "secret" in k.lower() or "authorization" in k.lower():
                    headers[k] = "***MASKED***"

    return clean


def make_trace_id() -> str:
    return f"trace_{int(time.time() * 1000)}"


def log_event(event_type: str, data: dict):
    try:
        payload = {
            "log_type": event_type,
            "timestamp": utc_now_iso(),
            "data": sanitize_for_json(data),
        }

        logger.info(json.dumps(payload, ensure_ascii=False, default=str))

    except Exception as e:
        logger.info(
            json.dumps(
                {
                    "log_type": "log_error",
                    "timestamp": utc_now_iso(),
                    "error": str(e),
                },
                ensure_ascii=False,
                default=str,
            )
        )


def log_trace(
    trace_id: str,
    step: str,
    data: Dict[str, Any] | None = None,
    level: str = "INFO",
):
    log_event(
        step,
        {
            "trace_id": trace_id,
            "level": level,
            **safe_payload_for_log(data or {}),
        },
    )