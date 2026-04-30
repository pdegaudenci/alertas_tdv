"""
Helpers de DataFrame para el panel Streamlit.

Centraliza transformaciones simples usadas por tablas del dashboard.
"""

from typing import Any, Dict, List

import pandas as pd


def dict_to_single_row_df(data: Dict[str, Any]) -> pd.DataFrame:
    """
    Convierte un diccionario en un DataFrame de una fila.
    """

    if not isinstance(data, dict) or not data:
        return pd.DataFrame()

    return pd.DataFrame([data])


def alerts_items_to_dataframe(items: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convierte la lista de alertas del backend/Supabase en DataFrame tabular.

    Mantiene las columnas usadas actualmente en el panel.
    """

    if not items:
        return pd.DataFrame()

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

    return pd.DataFrame(rows)