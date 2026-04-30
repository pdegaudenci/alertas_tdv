"""
Trade Engine del panel Streamlit.

Este archivo contiene la lógica original para:
- calcular TP / SL / BE / trailing,
- calcular riesgo y reward,
- calcular tamaño de posición real,
- clasificar riesgo, beneficio y R:R.

"""

from typing import Dict, Optional

import pandas as pd

from core.constants import (
    CAPITAL_EUR,
    RIESGO_POR_TRADE,
    APALANCAMIENTO,
    TP_REAL,
    COMISION,
)
from utils.math_utils import calcular_trailing


# ============================================================
# TRADE ENGINE / RISK ENGINE
# ============================================================

def compute_trade_levels(
    entrada: float,
    direccion: str,
    df_5m: pd.DataFrame,
    adx_5m: float
) -> Dict:
    """
    Calcula niveles de gestión del trade.

    Mantiene lógica original:
    - TP fijo 0.5%
    - Riesgo máximo 0.35%
    - SL estructural desde últimas 5 velas 5m
    - BE según dirección
    - trailing según ADX
    """

    tp_percent = 0.5 / 100
    max_risk = 0.0035

    if direccion == "LONG":
        tp = entrada * (1 + tp_percent)
        structural_sl = df_5m["low"].iloc[-5:].min()
        max_sl = entrada * (1 - max_risk)
        sl = max(structural_sl, max_sl)
        be = entrada * 1.0025
    else:
        tp = entrada * (1 - tp_percent)
        structural_sl = df_5m["high"].iloc[-5:].max()
        max_sl = entrada * (1 + max_risk)
        sl = min(structural_sl, max_sl)
        be = entrada * 0.9975

    trailing = calcular_trailing(adx_5m)

    risk_pct = abs((entrada - sl) / entrada) * 100 if entrada > 0 else 0
    reward_pct = abs((tp - entrada) / entrada) * 100 if entrada > 0 else 0
    rr = reward_pct / risk_pct if risk_pct > 0 else 0

    if risk_pct < 0.22:
        risk_label = "Muy bajo (ideal)"
    elif risk_pct < 0.35:
        risk_label = "Controlado"
    elif risk_pct < 0.55:
        risk_label = "Alto"
    else:
        risk_label = "Peligroso"

    if reward_pct < 0.35:
        reward_label = "Poco atractivo"
    elif reward_pct < 0.55:
        reward_label = "Normal"
    else:
        reward_label = "Excelente"

    if rr < 1.0:
        rr_label = "Malo"
    elif rr < 1.3:
        rr_label = "Justo"
    elif rr < 1.6:
        rr_label = "Bueno"
    else:
        rr_label = "Óptimo"

    return {
        "tp": tp,
        "sl": sl,
        "be": be,
        "trailing": trailing,
        "risk_pct": risk_pct,
        "reward_pct": reward_pct,
        "rr": rr,
        "risk_label": risk_label,
        "reward_label": reward_label,
        "rr_label": rr_label,
    }


def calcular_posicion_real(
    entrada: float,
    sl: float,
    tp: float
) -> Optional[Dict]:
    """
    Calcula tamaño de posición, margen, riesgo, beneficio y comisiones.

    Mantiene lógica original:
    - riesgo_eur = CAPITAL_EUR * RIESGO_POR_TRADE
    - posicion = riesgo_eur / riesgo_pct
    - margen = posicion / APALANCAMIENTO
    - beneficio_bruto = posicion * TP_REAL
    - comisiones = posicion * COMISION * 2
    """

    riesgo_eur = CAPITAL_EUR * RIESGO_POR_TRADE
    riesgo_pct = abs((entrada - sl) / entrada) if entrada > 0 else 0

    if riesgo_pct == 0:
        return None

    posicion = riesgo_eur / riesgo_pct
    margen_necesario = posicion / APALANCAMIENTO

    beneficio_bruto = posicion * TP_REAL
    comisiones = posicion * COMISION * 2
    beneficio_neto = beneficio_bruto - comisiones
    perdida_real = riesgo_eur

    return {
        "posicion": posicion,
        "margen": margen_necesario,
        "riesgo": perdida_real,
        "beneficio": beneficio_neto,
        "comisiones": comisiones,
    }