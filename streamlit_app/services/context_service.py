"""
Servicio de contexto operativo del panel Streamlit.

Este archivo contiene la lógica original para construir el contexto general
del mercado a partir de 1m, 5m, 15m y 1h.


"""

from typing import Dict

import pandas as pd

from core.constants import TP_BASE, SL_BASE
from utils.math_utils import safe_float, calcular_trailing


# ============================================================
# CONTEXTO / MARKET REGIME
# ============================================================

def construir_contexto(
    df_1m: pd.DataFrame,
    df_5m: pd.DataFrame,
    df_15m: pd.DataFrame,
    df_1h: pd.DataFrame
) -> Dict:
    """
    Construye el contexto operativo usado por el panel.

    Devuelve:
    - precio actual,
    - fase,
    - régimen,
    - estado EMA/VWAP,
    - timing LONG/SHORT,
    - validación de estructura,
    - probabilidad base,
    - EV,
    - trailing sugerido.
    """

    last1 = df_1m.iloc[-1]
    last5 = df_5m.iloc[-1]

    atr_mean = df_1m["atr"].rolling(50).mean().iloc[-1]
    atr_now = last1["atr"]
    ema200_slope = df_5m["ema200"].iloc[-1] - df_5m["ema200"].iloc[-6]

    adx_5m = safe_float(last5["adx"])
    di_plus = safe_float(last5["di_plus"])
    di_minus = safe_float(last5["di_minus"])
    st_dir = safe_float(last5["st_dir"])
    price_5m = safe_float(last5["close"])
    price_1m = safe_float(last1["close"])

    ema20 = safe_float(last1["ema20"])
    ema50 = safe_float(last1["ema50"])
    vwap = safe_float(last1["vwap"])
    atr = safe_float(last1["atr"])
    bb_width = safe_float(last1["bb_width"])
    roc = safe_float(last1["roc"])
    rsi_1m = safe_float(last1["rsi"])
    rsi_5m = safe_float(last5["rsi"])
    swing_high = safe_float(last1["swing_high"])
    swing_low = safe_float(last1["swing_low"])
    ema200_5m = safe_float(last5["ema200"])
    volatility = safe_float(last1["volatility"])

    upper = safe_float(last5["upper"])
    lower = safe_float(last5["lower"])
    mid = safe_float(last5["mid"])

    above_vwap = price_1m > vwap
    above_ema200 = price_5m > ema200_5m

    ema_bullish_stack = ema20 > ema50
    ema_bearish_stack = ema20 < ema50

    if adx_5m < 18 and atr_now < atr_mean * 0.9:
        market_regime = "RANGO"
    elif adx_5m < 22 and abs(ema200_slope) < 5:
        market_regime = "TRANSICIÓN"
    elif adx_5m >= 22 and atr_now >= atr_mean:
        market_regime = "EXPANSIÓN"
    elif adx_5m > 25 and abs(ema200_slope) > 8:
        market_regime = "TENDENCIA"
    else:
        market_regime = "NEUTRO"

    if st_dir == 1 and adx_5m > 22 and di_plus > di_minus:
        fase = "ALCISTA"
    elif st_dir == -1 and adx_5m > 22 and di_minus > di_plus:
        fase = "BAJISTA"
    elif 15 <= adx_5m <= 22:
        fase = "TRANSICIÓN"
    else:
        fase = "RANGO"

    espacio_long = price_5m <= lower or price_5m > upper
    espacio_short = price_5m >= upper or price_5m < lower

    candle_size = df_1m["high"].iloc[-1] - df_1m["low"].iloc[-1]
    avg_size = (df_1m["high"] - df_1m["low"]).rolling(20).mean().iloc[-1]

    vela_extendida = candle_size > 1.5 * avg_size if avg_size > 0 else False
    adx_cayendo = df_5m["adx"].iloc[-1] < df_5m["adx"].iloc[-2] < df_5m["adx"].iloc[-3]
    no_agotamiento = not vela_extendida and not adx_cayendo

    long_timing = rsi_1m > 52
    short_timing = rsi_1m < 48

    estructura_long = above_ema200 and above_vwap and ema_bullish_stack
    estructura_short = (not above_ema200) and (not above_vwap) and ema_bearish_stack

    long_valido = (
        fase in ["ALCISTA", "TRANSICIÓN"]
        and espacio_long
        and no_agotamiento
        and long_timing
        and estructura_long
    )

    short_valido = (
        fase in ["BAJISTA", "TRANSICIÓN"]
        and espacio_short
        and no_agotamiento
        and short_timing
        and estructura_short
    )

    tp_distance = price_1m * (TP_BASE / 100)
    atr_ratio = atr / tp_distance if tp_distance > 0 else 0

    score = 50

    if adx_5m > 25:
        score += 15
    elif adx_5m < 18:
        score -= 15

    if above_ema200:
        score += 10
    else:
        score -= 10

    if (price_1m > vwap and fase == "ALCISTA") or (price_1m < vwap and fase == "BAJISTA"):
        score += 10
    else:
        score -= 10

    if ema_bullish_stack or ema_bearish_stack:
        score += 8

    if 0.5 <= atr_ratio <= 1.2:
        score += 12
    elif atr_ratio < 0.35:
        score -= 15

    dist_to_high = abs(swing_high - price_1m) / price_1m if price_1m > 0 else None
    dist_to_low = abs(price_1m - swing_low) / price_1m if price_1m > 0 else None

    if long_valido and dist_to_high is not None and dist_to_high < 0.003:
        score -= 12

    if short_valido and dist_to_low is not None and dist_to_low < 0.003:
        score -= 12

    probabilidad = max(20, min(score, 95))

    p = probabilidad / 100
    EV = (p * TP_BASE) - ((1 - p) * SL_BASE)

    trailing = calcular_trailing(adx_5m)

    return {
        "price_1m": price_1m,
        "price_5m": price_5m,
        "ema20": ema20,
        "ema50": ema50,
        "vwap": vwap,
        "atr": atr,
        "atr_now": atr_now,
        "atr_mean": atr_mean,
        "atr_ratio": atr_ratio,
        "volatility": volatility,
        "rsi_1m": rsi_1m,
        "rsi_5m": rsi_5m,
        "roc": roc,
        "bb_width": bb_width,
        "swing_high": swing_high,
        "swing_low": swing_low,
        "ema200_5m": ema200_5m,
        "ema200_slope": ema200_slope,
        "adx_5m": adx_5m,
        "di_plus": di_plus,
        "di_minus": di_minus,
        "st_dir": st_dir,
        "upper": upper,
        "lower": lower,
        "mid": mid,
        "above_vwap": above_vwap,
        "above_ema200": above_ema200,
        "ema_bullish_stack": ema_bullish_stack,
        "ema_bearish_stack": ema_bearish_stack,
        "market_regime": market_regime,
        "fase": fase,
        "espacio_long": espacio_long,
        "espacio_short": espacio_short,
        "vela_extendida": vela_extendida,
        "adx_cayendo": adx_cayendo,
        "no_agotamiento": no_agotamiento,
        "long_timing": long_timing,
        "short_timing": short_timing,
        "estructura_long": estructura_long,
        "estructura_short": estructura_short,
        "long_valido": long_valido,
        "short_valido": short_valido,
        "probabilidad": probabilidad,
        "EV": EV,
        "dist_to_high": dist_to_high,
        "dist_to_low": dist_to_low,
        "trailing": trailing,
    }