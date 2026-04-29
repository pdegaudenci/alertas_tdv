"""
Servicio de Telegram.

Este archivo conserva la lógica  para:
- enviar mensajes por Telegram
- construir el mensaje de ENTRY VALIDADA OK
- enmascarar datos sensibles en logs

"""

from typing import Any, Dict
import traceback
import requests

from app.core.config import (
    TELEGRAM_ENABLED,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from app.core.logging import log_trace, mask_secret_value


def send_telegram_message(text: str, trace_id: str = "-") -> bool:
    if not TELEGRAM_ENABLED:
        log_trace(trace_id, "telegram_skipped", {"reason": "disabled"})
        return False

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log_trace(trace_id, "telegram_skipped", {"reason": "missing_env_vars"}, level="ERROR")
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        log_trace(trace_id, "telegram_sent_ok", {
            "chat_id": mask_secret_value(TELEGRAM_CHAT_ID),
            "status_code": response.status_code,
        })

        return True

    except Exception as e:
        log_trace(trace_id, "telegram_sent_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")
        return False


def build_telegram_entry_message(validation_result: Dict[str, Any]) -> str:
    validation = validation_result.get("validation", {}) if isinstance(validation_result, dict) else {}

    symbol = validation.get("symbol", "-")
    side = str(validation.get("side", "-")).upper()
    event = validation.get("event", "-")
    entry = validation.get("entry_price", "-")
    tp = validation.get("tp", "-")
    sl = validation.get("sl", "-")
    rr = validation.get("rr", "-")
    confidence = validation.get("confidence", "-")
    prob = validation.get("probability_tp_before_sl", "-")
    score = validation.get("score_external", "-")

    reasons = validation.get("reason", []) or []
    penalties = validation.get("penalties", []) or []

    reasons_txt = "\n".join([f"✅ {r}" for r in reasons[:5]]) if reasons else "Sin razones registradas"
    penalties_txt = "\n".join([f"⚠️ {p}" for p in penalties[:5]]) if penalties else "Sin penalizaciones"

    return f"""
🚀 <b>ENTRY VALIDADA OK</b>

<b>Symbol:</b> {symbol}
<b>Side:</b> {side}
<b>Event:</b> {event}

<b>Entry:</b> {entry}
<b>TP:</b> {tp}
<b>SL:</b> {sl}
<b>RR:</b> {rr}

<b>Confidence:</b> {confidence}%
<b>Prob TP antes SL:</b> {prob}
<b>Score externo:</b> {score}

<b>Razones:</b>
{reasons_txt}

<b>Penalizaciones:</b>
{penalties_txt}
""".strip()