"""
Servicio de validación MTF del panel Streamlit.

Este archivo contiene la lógica original para:
- evaluar alineación multi-timeframe,
- validar LONG / SHORT en 1H, 15M y 5M,
- medir apertura de EMAs en 5M.

"""

from typing import Dict, List, Tuple

import pandas as pd


# ============================================================
# MTF HELPERS
# ============================================================

def emas_abiertas_5m(
    direccion: str,
    ema9: float,
    ema20: float,
    ema50: float,
    price: float
) -> Tuple[bool, float, float]:
    """
    Evalúa si las EMAs 5m están ordenadas y suficientemente abiertas.

    Mantiene lógica original:
    - LONG: ema9 > ema20 > ema50
    - SHORT: ema9 < ema20 < ema50
    - distancia mínima: 0.00035 en ambos spreads
    """

    if direccion == "LONG":
        orden_correcto = ema9 > ema20 > ema50
    else:
        orden_correcto = ema9 < ema20 < ema50

    dist_1 = abs(ema9 - ema20) / price if price > 0 else 0
    dist_2 = abs(ema20 - ema50) / price if price > 0 else 0

    abiertas = (dist_1 > 0.00035) and (dist_2 > 0.00035)

    return orden_correcto and abiertas, dist_1, dist_2


def evaluar_mtf(
    direccion: str,
    mtf_1h: pd.DataFrame,
    mtf_15m: pd.DataFrame,
    mtf_5m: pd.DataFrame,
    mtf_1m: pd.DataFrame
) -> Tuple[bool, Dict[str, Tuple[bool, List[Dict]]]]:
    """
    Evalúa condiciones MTF para LONG o SHORT.

    Mantiene la lógica original del panel:
    - 1H: EMA50/EMA200, DI, ADX, RSI, ATR
    - 15M: precio vs EMA20, ADX subiendo, RSI, DI
    - 5M: abanico EMA9/20/50, ADX, DI
    """

    def check(cond: bool, texto: str, valor: str) -> Dict:
        return {
            "ok": cond,
            "texto": texto,
            "valor": valor,
        }

    resultado = {}
    valido_global = True

    # ========================================================
    # 1H
    # ========================================================
    last = mtf_1h.iloc[-1]
    prev = mtf_1h.iloc[-2]
    checks = []

    if direccion == "LONG":
        checks.append(check(last.ema50 > last.ema200, "EMA50 > EMA200", f"{last.ema50:.1f} vs {last.ema200:.1f}"))
        checks.append(check(last.di_plus > last.di_minus, "DI+ domina", f"{last.di_plus:.1f} vs {last.di_minus:.1f}"))
        checks.append(check(last.adx >= 18, "ADX ≥ 18", f"{last.adx:.1f}"))
        checks.append(check(last.rsi > 50, "RSI > 50", f"{last.rsi:.1f}"))
        checks.append(check(last.atr >= prev.atr, "ATR no decreciente", f"{last.atr:.1f} vs {prev.atr:.1f}"))
    else:
        checks.append(check(last.ema50 < last.ema200, "EMA50 < EMA200", f"{last.ema50:.1f} vs {last.ema200:.1f}"))
        checks.append(check(last.di_minus > last.di_plus, "DI- domina", f"{last.di_minus:.1f} vs {last.di_plus:.1f}"))
        checks.append(check(last.adx >= 18, "ADX ≥ 18", f"{last.adx:.1f}"))
        checks.append(check(last.rsi < 50, "RSI < 50", f"{last.rsi:.1f}"))
        checks.append(check(last.atr >= prev.atr, "ATR no decreciente", f"{last.atr:.1f} vs {prev.atr:.1f}"))

    valido_1h = all(c["ok"] for c in checks)
    resultado["1H"] = (valido_1h, checks)

    if not valido_1h:
        valido_global = False

    # ========================================================
    # 15M
    # ========================================================
    last = mtf_15m.iloc[-1]
    prev = mtf_15m.iloc[-2]
    checks = []

    if direccion == "LONG":
        checks.append(check(last.close > last.ema20, "Precio > EMA20", f"{last.close:.1f}"))
        checks.append(check(last.adx > prev.adx, "ADX subiendo", f"{last.adx:.1f} vs {prev.adx:.1f}"))
        checks.append(check(last.rsi > 50, "RSI > 50", f"{last.rsi:.1f}"))
        checks.append(check(last.di_plus > last.di_minus, "DI+ domina", f"{last.di_plus:.1f} vs {last.di_minus:.1f}"))
    else:
        checks.append(check(last.close < last.ema20, "Precio < EMA20", f"{last.close:.1f}"))
        checks.append(check(last.adx > prev.adx, "ADX subiendo", f"{last.adx:.1f} vs {prev.adx:.1f}"))
        checks.append(check(last.rsi < 50, "RSI < 50", f"{last.rsi:.1f}"))
        checks.append(check(last.di_minus > last.di_plus, "DI- domina", f"{last.di_minus:.1f} vs {last.di_plus:.1f}"))

    valido_15m = all(c["ok"] for c in checks)
    resultado["15M"] = (valido_15m, checks)

    if not valido_15m:
        valido_global = False

    # ========================================================
    # 5M
    # ========================================================
    last = mtf_5m.iloc[-1]
    ema9 = mtf_5m["ema9"].iloc[-1]
    checks = []

    if direccion == "LONG":
        checks.append(check(ema9 > last.ema20 > last.ema50, "Abanico alcista", f"{ema9:.1f}>{last.ema20:.1f}>{last.ema50:.1f}"))
        checks.append(check(last.adx > 20, "ADX > 20", f"{last.adx:.1f}"))
        checks.append(check(last.di_plus > last.di_minus, "DI+ domina", f"{last.di_plus:.1f} vs {last.di_minus:.1f}"))
    else:
        checks.append(check(ema9 < last.ema20 < last.ema50, "Abanico bajista", f"{ema9:.1f}<{last.ema20:.1f}<{last.ema50:.1f}"))
        checks.append(check(last.adx > 20, "ADX > 20", f"{last.adx:.1f}"))
        checks.append(check(last.di_minus > last.di_plus, "DI- domina", f"{last.di_minus:.1f} vs {last.di_plus:.1f}"))

    valido_5m = all(c["ok"] for c in checks)
    resultado["5M"] = (valido_5m, checks)

    if not valido_5m:
        valido_global = False

    return valido_global, resultado