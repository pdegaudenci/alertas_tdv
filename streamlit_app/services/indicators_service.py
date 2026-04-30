"""
Indicadores técnicos propios del panel Streamlit.

Este archivo contiene las funciones originales del panel monolítico para
calcular indicadores sin pandas_ta.

"""

from typing import Tuple

import numpy as np
import pandas as pd


# ============================================================
# INDICADORES PROPIOS
# ============================================================

def ema(series: pd.Series, length: int) -> pd.Series:
    """
    Calcula EMA usando pandas ewm.

    Mantiene la lógica original del panel:
    series.ewm(span=length, adjust=False).mean()
    """

    return series.ewm(span=length, adjust=False).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """
    Calcula RSI usando medias exponenciales.

    Mantiene la lógica original del panel.
    """

    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))

    return out.fillna(50)


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 14
) -> pd.Series:
    """
    Calcula ATR usando True Range + ewm.

    Mantiene la lógica original del panel.
    """

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return tr.ewm(alpha=1 / length, adjust=False).mean()


def roc(series: pd.Series, length: int = 5) -> pd.Series:
    """
    Calcula Rate of Change en porcentaje.

    Mantiene la lógica original:
    ((series / series.shift(length)) - 1.0) * 100.0
    """

    return ((series / series.shift(length)) - 1.0) * 100.0


def bbands(
    series: pd.Series,
    length: int = 20,
    std_mult: float = 2.0
) -> pd.DataFrame:
    """
    Calcula Bollinger Bands.

    Devuelve columnas:
    - BBM
    - BBU
    - BBL
    """

    basis = series.rolling(length).mean()
    dev = series.rolling(length).std(ddof=0)

    upper = basis + std_mult * dev
    lower = basis - std_mult * dev

    return pd.DataFrame(
        {
            "BBM": basis,
            "BBU": upper,
            "BBL": lower,
        },
        index=series.index,
    )


def vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series
) -> pd.Series:
    """
    Calcula VWAP acumulado.

    Mantiene la lógica original del panel.
    """

    typical_price = (high + low + close) / 3.0
    tpv = typical_price * volume

    cum_tpv = tpv.cumsum()
    cum_vol = volume.cumsum().replace(0, np.nan)

    return cum_tpv / cum_vol


def adx_dmi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 14
) -> pd.DataFrame:
    """
    Calcula ADX, DMP y DMN.

    Mantiene la lógica original del panel:
    - DM+ / DM-
    - ATR basado en función atr()
    - medias exponenciales
    """

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=high.index,
    )

    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=high.index,
    )

    atr_series = atr(high, low, close, length)

    plus_di = 100 * (
        plus_dm.ewm(alpha=1 / length, adjust=False).mean()
        / atr_series.replace(0, np.nan)
    )

    minus_di = 100 * (
        minus_dm.ewm(alpha=1 / length, adjust=False).mean()
        / atr_series.replace(0, np.nan)
    )

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_series = dx.ewm(alpha=1 / length, adjust=False).mean()

    return pd.DataFrame(
        {
            "ADX": adx_series.fillna(0),
            "DMP": plus_di.fillna(0),
            "DMN": minus_di.fillna(0),
        },
        index=high.index,
    )


def supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 10,
    multiplier: float = 3.0
) -> pd.DataFrame:
    """
    Calcula Supertrend.

    Mantiene la lógica original del panel.
    Devuelve:
    - SUPERT
    - SUPERTd
    """

    atr_series = atr(high, low, close, length)
    hl2 = (high + low) / 2.0

    basic_upperband = hl2 + multiplier * atr_series
    basic_lowerband = hl2 - multiplier * atr_series

    final_upperband = basic_upperband.copy()
    final_lowerband = basic_lowerband.copy()

    for i in range(1, len(close)):
        if (
            basic_upperband.iloc[i] < final_upperband.iloc[i - 1]
            or close.iloc[i - 1] > final_upperband.iloc[i - 1]
        ):
            final_upperband.iloc[i] = basic_upperband.iloc[i]
        else:
            final_upperband.iloc[i] = final_upperband.iloc[i - 1]

        if (
            basic_lowerband.iloc[i] > final_lowerband.iloc[i - 1]
            or close.iloc[i - 1] < final_lowerband.iloc[i - 1]
        ):
            final_lowerband.iloc[i] = basic_lowerband.iloc[i]
        else:
            final_lowerband.iloc[i] = final_lowerband.iloc[i - 1]

    supertrend_line = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)

    if len(close) > 0:
        supertrend_line.iloc[0] = final_upperband.iloc[0]
        direction.iloc[0] = -1

    for i in range(1, len(close)):
        if supertrend_line.iloc[i - 1] == final_upperband.iloc[i - 1]:
            if close.iloc[i] > final_upperband.iloc[i]:
                direction.iloc[i] = 1
                supertrend_line.iloc[i] = final_lowerband.iloc[i]
            else:
                direction.iloc[i] = -1
                supertrend_line.iloc[i] = final_upperband.iloc[i]
        else:
            if close.iloc[i] < final_lowerband.iloc[i]:
                direction.iloc[i] = -1
                supertrend_line.iloc[i] = final_upperband.iloc[i]
            else:
                direction.iloc[i] = 1
                supertrend_line.iloc[i] = final_lowerband.iloc[i]

    return pd.DataFrame(
        {
            "SUPERT": supertrend_line,
            "SUPERTd": direction.fillna(-1),
        },
        index=close.index,
    )


# ============================================================
# PREPARACIÓN DE TIMEFRAMES
# ============================================================

def preparar_tf(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara un dataframe genérico de timeframe superior.

    Agrega:
    - adx
    - di_plus
    - di_minus
    - rsi
    - ema9
    - ema20
    - ema50
    - ema200
    - atr
    """

    df = df.copy()

    adx = adx_dmi(df["high"], df["low"], df["close"], length=14)
    df["adx"] = adx["ADX"]
    df["di_plus"] = adx["DMP"]
    df["di_minus"] = adx["DMN"]

    df["rsi"] = rsi(df["close"], length=14)
    df["ema9"] = ema(df["close"], length=9)
    df["ema20"] = ema(df["close"], length=20)
    df["ema50"] = ema(df["close"], length=50)
    df["ema200"] = ema(df["close"], length=200)
    df["atr"] = atr(df["high"], df["low"], df["close"], length=14)

    return df


def preparar_1m(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara dataframe de 1 minuto.

    Agrega indicadores específicos usados por el panel:
    - adx
    - di_plus
    - di_minus
    - rsi length 9
    - ema20
    - ema50
    - atr
    - roc
    - vol_ma
    - vol_strength
    - vwap
    - bb_width
    - volatility
    - swing_high
    - swing_low
    """

    df = df.copy()

    adx = adx_dmi(df["high"], df["low"], df["close"], length=14)
    df["adx"] = adx["ADX"]
    df["di_plus"] = adx["DMP"]
    df["di_minus"] = adx["DMN"]

    df["rsi"] = rsi(df["close"], length=9)

    df["ema20"] = ema(df["close"], length=20)
    df["ema50"] = ema(df["close"], length=50)

    df["atr"] = atr(df["high"], df["low"], df["close"], length=14)

    df["roc"] = roc(df["close"], length=5)

    df["vol_ma"] = df["volume"].rolling(20).mean()
    df["vol_strength"] = np.where(
        df["vol_ma"] > 0,
        df["volume"] / df["vol_ma"],
        0.0,
    )

    df["vwap"] = vwap(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        volume=df["volume"],
    )

    bb = bbands(df["close"], length=20, std_mult=2.0)
    df["bb_width"] = (bb["BBU"] - bb["BBL"]) / df["close"]

    df["volatility"] = df["atr"] / df["close"]

    df["swing_high"] = df["high"].rolling(20).max()
    df["swing_low"] = df["low"].rolling(20).min()

    return df


def preparar_5m_contexto(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara dataframe 5m de contexto.

    Agrega:
    - st_dir
    - upper
    - lower
    - mid
    """

    df = df.copy()

    st_data = supertrend(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        length=10,
        multiplier=3.0,
    )

    df["st_dir"] = st_data["SUPERTd"]

    df["upper"] = df["high"].rolling(100).max()
    df["lower"] = df["low"].rolling(100).min()
    df["mid"] = (df["upper"] + df["lower"]) / 2.0

    return df