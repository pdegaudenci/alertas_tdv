"""
Probability Service del panel Streamlit.

Este archivo contiene la lógica original para:
- estimar probabilidad real de alcanzar TP,
- estimar probabilidad de rentabilidad,

"""

from typing import List, Tuple


# ============================================================
# PROBABILIDAD TP / RENTABILIDAD
# ============================================================

def probabilidad_tp_real(
    direccion: str,
    prob_mercado: float,
    prob_entry: float,
    rr: float,
    atr_ratio: float,
    adx: float,
    rsi: float,
    lrs: float,
    market_regime: str,
    liquidity_attraction: str,
    ema_stack: bool,
    above_vwap: bool
) -> Tuple[float, List[Tuple[str, str, str]]]:
    """
    Calcula probabilidad real de alcanzar TP.

    Mantiene lógica original:
    - Base = prob_mercado * 0.55 + prob_entry * 0.45
    - Ajustes por RR, ATR, ADX, RSI, LRS, liquidez, EMA/VWAP y régimen.
    """

    debug = []
    p = (prob_mercado * 0.55 + prob_entry * 0.45)

    debug.append(("Base entorno+entrada", f"{p:.1f}", "Neutro"))

    if rr >= 1.6:
        p += 8
        debug.append(("R:R óptimo", f"{rr:.2f}", "+8"))
    elif rr >= 1.3:
        p += 4
        debug.append(("R:R bueno", f"{rr:.2f}", "+4"))
    elif rr < 1.0:
        p -= 12
        debug.append(("R:R malo", f"{rr:.2f}", "-12"))

    if 0.5 <= atr_ratio <= 1.3:
        p += 10
        debug.append(("ATR suficiente", f"{atr_ratio:.2f}", "+10"))
    elif atr_ratio < 0.35:
        p -= 18
        debug.append(("ATR insuficiente", f"{atr_ratio:.2f}", "-18"))
    elif atr_ratio > 2.2:
        p -= 8
        debug.append(("ATR demasiado volátil", f"{atr_ratio:.2f}", "-8"))

    if adx > 28:
        p += 8
        debug.append(("ADX fuerte", f"{adx:.1f}", "+8"))
    elif adx < 18:
        p -= 12
        debug.append(("ADX débil", f"{adx:.1f}", "-12"))

    if direccion == "LONG":
        if rsi > 56:
            p += 6
            debug.append(("Timing RSI alcista", f"{rsi:.1f}", "+6"))
        elif rsi < 50:
            p -= 8
            debug.append(("RSI contra tendencia", f"{rsi:.1f}", "-8"))
    else:
        if rsi < 44:
            p += 6
            debug.append(("Timing RSI bajista", f"{rsi:.1f}", "+6"))
        elif rsi > 50:
            p -= 8
            debug.append(("RSI contra tendencia", f"{rsi:.1f}", "-8"))

    penalty = lrs * 0.35
    p -= penalty
    debug.append(("Liquidity Risk", f"{lrs:.1f}", f"-{round(penalty, 1)}"))

    if direccion == "LONG" and liquidity_attraction == "DOWN":
        p -= 6
        debug.append(("Atracción contraria", liquidity_attraction, "-6"))

    if direccion == "SHORT" and liquidity_attraction == "UP":
        p -= 6
        debug.append(("Atracción contraria", liquidity_attraction, "-6"))

    if ema_stack and above_vwap:
        p += 6
        debug.append(("Estructura institucional", "EMA+VWAP", "+6"))

    if market_regime == "TENDENCIA":
        p += 10
        debug.append(("Régimen tendencia", market_regime, "+10"))
    elif market_regime == "EXPANSIÓN":
        p += 6
        debug.append(("Régimen expansión", market_regime, "+6"))
    elif market_regime == "RANGO":
        p -= 20
        debug.append(("Mercado lateral", market_regime, "-20"))

    p = max(5, min(p, 95))

    return p, debug


def probabilidad_rentable(prob_tp: float, rr: float) -> float:
    """
    Calcula probabilidad visual de rentabilidad.

    Mantiene lógica original:
    p = prob_tp / 100
    ev = (p * rr) - (1 - p)
    rentable_prob = (ev + 1) / 2 * 100
    """

    p = prob_tp / 100
    ev = (p * rr) - (1 - p)

    rentable_prob = (ev + 1) / 2 * 100
    rentable_prob = max(0, min(rentable_prob, 100))

    return rentable_prob