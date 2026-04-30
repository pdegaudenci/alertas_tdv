"""
Liquidity Engine del panel Streamlit.

Este archivo contiene la lógica original del panel para:
- detectar pivots,
- contar toques,
- agrupar zonas,
- calcular riesgo de liquidez,
- explicar riesgo por dirección,
- construir el mapa de liquidez operativo.

"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from utils.math_utils import safe_float


# ============================================================
# LIQUIDITY ENGINE
# ============================================================

def detectar_pivots(df: pd.DataFrame, order: int = 12) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detecta pivots locales de máximos y mínimos.

    Mantiene lógica original:
    - highs con argrelextrema(np.greater)
    - lows con argrelextrema(np.less)
    """

    highs = df["high"].values
    lows = df["low"].values

    pivot_highs = argrelextrema(highs, np.greater, order=order)[0]
    pivot_lows = argrelextrema(lows, np.less, order=order)[0]

    return pivot_highs, pivot_lows


def contar_toques(
    df: pd.DataFrame,
    nivel: float,
    atr: float,
    factor: float = 0.15
) -> int:
    """
    Cuenta cuántas velas tocaron un nivel dentro de una tolerancia basada en ATR.

    Mantiene lógica original:
    tolerancia = atr * factor
    """

    if atr <= 0:
        return 0

    tolerancia = atr * factor
    toques = 0

    for _, row in df.iterrows():
        if abs(row["high"] - nivel) <= tolerancia or abs(row["low"] - nivel) <= tolerancia:
            toques += 1

    return toques


def agrupar_zonas(
    niveles: List[float],
    tolerancia_pct: float = 0.0008
) -> List[Tuple[float, float]]:
    """
    Agrupa niveles cercanos en zonas.

    Mantiene lógica original:
    - Ordena niveles
    - Agrupa por distancia relativa menor a tolerancia_pct
    """

    if len(niveles) == 0:
        return []

    niveles = sorted(niveles)
    zonas = []
    zona_actual = [niveles[0]]

    for lvl in niveles[1:]:
        ref = np.mean(zona_actual)

        if ref != 0 and abs(lvl - ref) / ref < tolerancia_pct:
            zona_actual.append(lvl)
        else:
            zonas.append((min(zona_actual), max(zona_actual)))
            zona_actual = [lvl]

    zonas.append((min(zona_actual), max(zona_actual)))

    return zonas


def market_liquidity_risk(
    price: float,
    atr: float,
    nearest_resistance: Optional[float],
    nearest_support: Optional[float],
    strong_resistances: List[float],
    strong_supports: List[float],
    liquidity_attraction: str
) -> float:
    """
    Calcula riesgo general de liquidez del mercado.

    Mantiene lógica original y escala:
    - máximo 80
    - mínimo 0
    """

    if atr == 0:
        return 50.0

    if nearest_resistance is None:
        return 10.0

    if nearest_support is None:
        return 10.0

    risk = 0.0

    dist_up_atr = (nearest_resistance - price) / atr
    dist_down_atr = (price - nearest_support) / atr

    if dist_up_atr < 0.7:
        risk += 30
    elif dist_up_atr < 1.2:
        risk += 15

    if dist_down_atr < 0.7:
        risk += 30
    elif dist_down_atr < 1.2:
        risk += 15

    if len(strong_resistances) >= 2:
        risk += 15

    if len(strong_supports) >= 2:
        risk += 15

    if liquidity_attraction in ["UP", "DOWN"]:
        risk += 10

    return max(0, min(risk, 80))


def liquidity_risk_explained(
    direccion,
    price,
    atr,
    nearest_resistance,
    nearest_support,
    liquidity_attraction,
    strong_resistances,
    strong_supports
):
    """
    Calcula y explica el riesgo de liquidez para una dirección concreta.

    Mantiene lógica original:
    - LONG penaliza stops inferiores cercanos y atracción DOWN
    - SHORT penaliza stops superiores cercanos y atracción UP
    """

    report = []

    if nearest_resistance is None or nearest_support is None or atr == 0:
        return {
            "score": 40,
            "label": "NEUTRO",
            "favorable": False,
            "debug": ["Datos insuficientes de liquidez"],
        }

    risk = 0.0

    dist_up_atr = (nearest_resistance - price) / atr
    dist_down_atr = (price - nearest_support) / atr

    if direccion == "LONG":
        if dist_down_atr < 0.7:
            risk += 35
            report.append("Stops de LONGS muy cercanos → probable sweep bajista")
        elif dist_down_atr < 1.2:
            risk += 20
            report.append("Liquidez inferior cercana")

        if dist_up_atr < 1.5:
            risk -= 10
            report.append("Objetivo alcista cercano (favorece TP)")

    if direccion == "SHORT":
        if dist_up_atr < 0.7:
            risk += 35
            report.append("Stops de SHORTS muy cercanos → probable sweep alcista")
        elif dist_up_atr < 1.2:
            risk += 20
            report.append("Liquidez superior cercana")

        if dist_down_atr < 1.5:
            risk -= 10
            report.append("Objetivo bajista cercano (favorece TP)")

    if direccion == "LONG" and liquidity_attraction == "DOWN":
        risk += 25
        report.append("El mercado quiere barrer LONGS primero")

    if direccion == "SHORT" and liquidity_attraction == "UP":
        risk += 25
        report.append("El mercado quiere barrer SHORTS primero")

    if direccion == "LONG" and len(strong_resistances) >= 2:
        risk += 20
        report.append("Resistencias institucionales arriba")

    if direccion == "SHORT" and len(strong_supports) >= 2:
        risk += 20
        report.append("Soportes institucionales abajo")

    risk = max(0, min(risk, 80))

    if risk <= 15:
        label = "EXCELENTE"
        favorable = True
    elif risk <= 30:
        label = "FAVORABLE"
        favorable = True
    elif risk <= 45:
        label = "NEUTRO PELIGROSO"
        favorable = False
    elif risk <= 60:
        label = "DESFAVORABLE"
        favorable = False
    else:
        label = "MUY PELIGROSO (SWEEP PROBABLE)"
        favorable = False

    return {
        "score": risk,
        "label": label,
        "favorable": favorable,
        "debug": report,
    }


def construir_liquidity_engine(
    df_1m: pd.DataFrame,
    atr: float,
    price: float
) -> Dict:
    """
    Construye el mapa de liquidez operativo del panel.

    Devuelve:
    - nearest_resistance
    - nearest_support
    - distancias
    - zonas fuertes
    - atracción probable
    - market_lrs
    - zonas agrupadas
    """

    pivot_highs, pivot_lows = detectar_pivots(df_1m)

    liquidity_above = []
    liquidity_below = []

    for i in pivot_highs:
        if i < len(df_1m) and safe_float(df_1m.iloc[i]["vol_strength"]) > 1.5:
            liquidity_above.append(float(df_1m.iloc[i]["high"]))

    for i in pivot_lows:
        if i < len(df_1m) and safe_float(df_1m.iloc[i]["vol_strength"]) > 1.5:
            liquidity_below.append(float(df_1m.iloc[i]["low"]))

    resistances = [lvl for lvl in liquidity_above if lvl > price]
    supports = [lvl for lvl in liquidity_below if lvl < price]

    nearest_resistance = min(resistances) if len(resistances) > 0 else None
    nearest_support = max(supports) if len(supports) > 0 else None

    if nearest_resistance is not None:
        dist_up = nearest_resistance - price
        dist_up_pct = dist_up / price
    else:
        dist_up = None
        dist_up_pct = None

    if nearest_support is not None:
        dist_down = price - nearest_support
        dist_down_pct = dist_down / price
    else:
        dist_down = None
        dist_down_pct = None

    strong_resistances = []
    strong_supports = []

    scope = df_1m.tail(300)

    for lvl in liquidity_above:
        touches = contar_toques(scope, lvl, atr)
        if touches >= 3:
            strong_resistances.append(lvl)

    for lvl in liquidity_below:
        touches = contar_toques(scope, lvl, atr)
        if touches >= 3:
            strong_supports.append(lvl)

    if nearest_resistance is None and nearest_support is None:
        liquidity_attraction = "NONE"
    elif nearest_support is None:
        liquidity_attraction = "UP"
    elif nearest_resistance is None:
        liquidity_attraction = "DOWN"
    else:
        up_score = 1 / dist_up_pct if dist_up_pct and dist_up_pct > 0 else 0
        down_score = 1 / dist_down_pct if dist_down_pct and dist_down_pct > 0 else 0

        if nearest_resistance in strong_resistances:
            up_score *= 1.4

        if nearest_support in strong_supports:
            down_score *= 1.4

        liquidity_attraction = "UP" if up_score > down_score else "DOWN"

    market_clean = True

    if dist_up_pct is not None and dist_up_pct < 0.0015:
        market_clean = False

    if dist_down_pct is not None and dist_down_pct < 0.0015:
        market_clean = False

    market_lrs = market_liquidity_risk(
        price=price,
        atr=atr,
        nearest_resistance=nearest_resistance,
        nearest_support=nearest_support,
        strong_resistances=strong_resistances,
        strong_supports=strong_supports,
        liquidity_attraction=liquidity_attraction,
    )

    return {
        "nearest_resistance": nearest_resistance,
        "nearest_support": nearest_support,
        "dist_up": dist_up,
        "dist_down": dist_down,
        "dist_up_pct": dist_up_pct,
        "dist_down_pct": dist_down_pct,
        "strong_resistances": strong_resistances,
        "strong_supports": strong_supports,
        "liquidity_attraction": liquidity_attraction,
        "market_clean": market_clean,
        "market_lrs": market_lrs,
        "resistance_zones": agrupar_zonas(strong_resistances),
        "support_zones": agrupar_zonas(strong_supports),
    }