"""
Backtest e histórico del panel Streamlit.

Este archivo contiene la lógica original para:
- guardar señales en CSV,
- buscar condiciones similares,
- calcular probabilidad histórica,
- ejecutar backtest rápido 1M.

"""

import os
from datetime import datetime
from typing import List, Tuple

import pandas as pd

from core.config import LOG_FILE
from core.constants import TP_BASE, SL_BASE


# ============================================================
# LOGGING / BACKTEST
# ============================================================

def log_signal(
    tipo: str,
    prob: float,
    fase: str,
    adx: float,
    rsi_1m: float
) -> None:
    """
    Guarda una señal local en CSV.

    Mantiene lógica original:
    - Si existe LOG_FILE, append sin header.
    - Si no existe, crea el archivo.
    """

    row = {
        "time": datetime.now(),
        "tipo": tipo,
        "fase": fase,
        "adx": adx,
        "rsi_1m": rsi_1m,
        "probabilidad": prob,
    }

    df = pd.DataFrame([row])

    if os.path.exists(LOG_FILE):
        df.to_csv(LOG_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(LOG_FILE, index=False)


def condiciones_similares(
    df: pd.DataFrame,
    direction: str
) -> List[int]:
    """
    Busca condiciones históricas similares.

    Mantiene lógica original:
    - Ventana desde i=50 hasta len(df)-15
    - Condiciones según ADX, DI y RSI
    """

    condiciones = []

    required_cols = ["adx", "di_plus", "di_minus", "rsi"]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        return condiciones

    direction = direction.upper()

    for i in range(50, len(df) - 15):
        row = df.iloc[i]

        if pd.isna(row["adx"]) or pd.isna(row["di_plus"]) or pd.isna(row["di_minus"]) or pd.isna(row["rsi"]):
            continue

        if direction == "SHORT":
            cond = (
                20 <= row["adx"] <= 30
                and row["di_minus"] > row["di_plus"]
                and row["rsi"] < 50
            )
        else:
            cond = (
                20 <= row["adx"] <= 30
                and row["di_plus"] > row["di_minus"]
                and row["rsi"] > 50
            )

        if cond:
            condiciones.append(i)

    return condiciones


def probabilidad_historica(
    df: pd.DataFrame,
    direction: str
) -> float:
    """
    Calcula probabilidad histórica por condiciones similares.

    Mantiene lógica original:
    - SHORT TP 0.995 / SL 1.0035
    - LONG TP 1.005 / SL 0.9965
    - Evalúa 15 velas futuras
    """

    indices = condiciones_similares(df, direction)

    wins = 0
    total = 0

    for i in indices:
        entry = df["close"].iloc[i]

        if direction.upper() == "SHORT":
            tp = entry * 0.995
            sl = entry * 1.0035
        else:
            tp = entry * 1.005
            sl = entry * 0.9965

        future = df.iloc[i + 1:i + 15]

        hit_tp = False
        hit_sl = False

        for _, row in future.iterrows():
            if direction.upper() == "SHORT":
                if row["low"] <= tp:
                    hit_tp = True
                    break
                if row["high"] >= sl:
                    hit_sl = True
                    break
            else:
                if row["high"] >= tp:
                    hit_tp = True
                    break
                if row["low"] <= sl:
                    hit_sl = True
                    break

        if hit_tp:
            wins += 1

        if hit_tp or hit_sl:
            total += 1

    return (wins / total * 100) if total > 0 else 0.0


def backtest(
    df: pd.DataFrame,
    direction: str = "long"
) -> Tuple[int, int, float, float]:
    """
    Ejecuta backtest rápido 1M.

    Mantiene lógica original:
    - i desde 50 hasta len(df)-10
    - horizonte futuro 10 velas
    - TP_BASE / SL_BASE
    - capital inicial 100
    """

    wins = 0
    losses = 0
    capital = 100.0

    for i in range(50, len(df) - 10):
        entry = df["close"].iloc[i]

        tp = entry * (1 + TP_BASE / 100) if direction == "long" else entry * (1 - TP_BASE / 100)
        sl = entry * (1 - SL_BASE / 100) if direction == "long" else entry * (1 + SL_BASE / 100)

        future = df.iloc[i + 1:i + 10]

        hit_tp = False
        hit_sl = False

        for _, row in future.iterrows():
            if direction == "long":
                if row["high"] >= tp:
                    hit_tp = True
                    break
                if row["low"] <= sl:
                    hit_sl = True
                    break
            else:
                if row["low"] <= tp:
                    hit_tp = True
                    break
                if row["high"] >= sl:
                    hit_sl = True
                    break

        if hit_tp:
            wins += 1
            capital *= 1.005
        elif hit_sl:
            losses += 1
            capital *= 0.997

    total = wins + losses
    winrate = wins / total * 100 if total > 0 else 0

    return wins, losses, winrate, capital