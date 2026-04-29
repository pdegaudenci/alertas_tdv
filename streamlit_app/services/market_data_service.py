"""
Servicio de market data para el panel Streamlit.

Este archivo contiene las funciones originales de descarga de datos desde Binance.

"""

from typing import Dict

import pandas as pd
import requests

from core.config import BINANCE_BASE_URLS


# ============================================================
# BINANCE DATA
# ============================================================

def get_klines(
    symbol: str,
    interval: str,
    limit: int = 500
) -> pd.DataFrame:
    """
    Descarga klines desde Binance.

    Mantiene la lógica original:
    - Usa data-api.binance.vision como endpoint principal.
    - Devuelve DataFrame indexado por time UTC.
    - Columnas finales: open, high, low, close, volume.
    """

    url = f"{BINANCE_BASE_URLS[0]}/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame(
        data,
        columns=[
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "qav",
            "num_trades",
            "taker_base_vol",
            "taker_quote_vol",
            "ignore",
        ],
    )

    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df.set_index("time", inplace=True)

    df = df[["open", "high", "low", "close", "volume"]].astype(float)

    return df


def obtener_datos_binance(symbol: str) -> Dict[str, pd.DataFrame]:
    """
    Descarga datos de Binance para los timeframes usados por el panel.

    Mantiene la lógica original:
    - 1m: 600 velas
    - 5m: 600 velas
    - 15m: 600 velas
    - 1h: 600 velas
    """

    data = {
        "1m": get_klines(symbol, "1m", 600),
        "5m": get_klines(symbol, "5m", 600),
        "15m": get_klines(symbol, "15m", 600),
        "1h": get_klines(symbol, "1h", 600),
    }

    return data