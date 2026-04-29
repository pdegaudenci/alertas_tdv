"""
Alert View Service del panel Streamlit.

Este archivo prepara datos de alertas para visualización.

Responsabilidad:
- Extraer campos principales de /api/latest.
- Preparar resumen de última alerta.
- Preparar filas del histórico Supabase.
- Evitar que app.py tenga lógica repetida de transformación.

"""

from typing import Any, Dict, List

import pandas as pd


def unwrap_latest_response(latest_response: Any) -> Dict[str, Any]:
    """
    Normaliza la respuesta de /api/latest.

    Mantiene la lógica usada actualmente en app.py:

    latest_data = latest_response.get("data", latest_response)
    """

    if not isinstance(latest_response, dict):
        return {}

    return latest_response.get("data", latest_response)


def extract_latest_alert_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae resumen principal de la última alerta.

    Usa exactamente los campos que ya se muestran en app.py.
    """

    if not isinstance(data, dict):
        return {}

    return {
        "ok": data.get("ok"),
        "symbol": data.get("symbol", "-"),
        "side": data.get("side", "-"),
        "setup": data.get("setup", "-"),
        "event": data.get("event", "-"),
        "quality_score": data.get("quality_score", "-"),
        "timeframe": data.get("timeframe", "-"),
        "price": data.get("price", "-"),
        "phase": data.get("phase", "-"),
        "regime": data.get("regime", "-"),
        "phase_5m": data.get("phase_5m", "-"),
        "strength_5m": data.get("strength_5m", "-"),
        "received_at": data.get("received_at", "-"),
        "payload": data.get("payload", {}) or {},
        "validation": data.get("validation", {}) or {},
        "trace_id": data.get("trace_id", "-"),
        "message_type": data.get("message_type", "-"),
        "event_uid": data.get("event_uid", "-"),
    }


def build_latest_alert_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara las métricas usadas en la sección Última alerta recibida.
    """

    summary = extract_latest_alert_summary(data)

    return {
        "row_1": {
            "Símbolo": summary.get("symbol", "-"),
            "Side": str(summary.get("side", "-")).upper(),
            "Evento": summary.get("event", "-"),
            "TF": summary.get("timeframe", "-"),
        },
        "row_2": {
            "Precio": summary.get("price", "-"),
            "Phase": summary.get("phase", "-"),
            "Regime": summary.get("regime", "-"),
            "Quality": summary.get("quality_score", "-"),
        },
        "details": {
            "Setup": summary.get("setup", "-"),
            "Phase 5m": summary.get("phase_5m", "-"),
            "Strength 5m": summary.get("strength_5m", "-"),
            "Recibida": summary.get("received_at", "-"),
            "Trace ID": summary.get("trace_id", "-"),
            "Message type": summary.get("message_type", "-"),
            "Event UID": summary.get("event_uid", "-"),
        },
    }


def build_alert_history_rows(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convierte items del histórico Supabase en filas tabulares.

    Mantiene exactamente las columnas usadas actualmente en app.py.
    """

    rows = []

    for item in items:
        rows.append({
            "created_at": item.get("created_at"),
            "symbol": item.get("symbol"),
            "tf": item.get("tf"),
            "event": item.get("event"),
            "side": item.get("side"),
            "status": item.get("status"),
            "setup_id": item.get("setup_id"),
            "phase": item.get("phase"),
            "regime": item.get("regime"),
            "dir_state": item.get("dir_state"),
            "mov_state": item.get("mov_state"),
            "liq_state": item.get("liq_state"),
            "htf_phase": item.get("htf_phase"),
            "trigger_alignment": item.get("trigger_alignment"),
            "spread_bps": item.get("spread_bps"),
            "book_imbalance": item.get("book_imbalance"),
        })

    return rows


def build_alert_history_dataframe(items: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Devuelve DataFrame del histórico de alertas.

    Si no hay items, devuelve DataFrame vacío.
    """

    rows = build_alert_history_rows(items)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def build_alert_expander_title(index: int, item: Dict[str, Any]) -> str:
    """
    Construye el título del expander de histórico.

    Mantiene formato actual:
    {idx+1}. {created_at} | {symbol} | {event} | {SIDE}
    """

    return (
        f"{index + 1}. {item.get('created_at', '-')} | "
        f"{item.get('symbol', '-')} | "
        f"{item.get('event', '-')} | "
        f"{str(item.get('side', '-')).upper()}"
    )


def extract_alert_detail(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae los campos mostrados en cada expander del histórico.
    """

    if not isinstance(item, dict):
        return {}

    return {
        "setup_id": item.get("setup_id"),
        "status": item.get("status"),
        "phase": item.get("phase"),
        "regime": item.get("regime"),
        "dir_state": item.get("dir_state"),
        "mov_state": item.get("mov_state"),
        "liq_state": item.get("liq_state"),
        "htf_phase": item.get("htf_phase"),
        "trigger_alignment": item.get("trigger_alignment"),
        "spread_bps": item.get("spread_bps"),
        "book_imbalance": item.get("book_imbalance"),
        "normalized_payload": item.get("normalized_payload", {}),
        "technical_state": item.get("technical_state", {}),
        "microstructure_state": item.get("microstructure_state", {}),
        "raw_payload": item.get("raw_payload", {}),
    }