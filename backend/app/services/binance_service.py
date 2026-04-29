"""
Servicio cliente de Binance.

Este archivo conserva la lógica original de index.py para consultar Binance:
- klines
- order book depth
- aggTrades

"""

from typing import Any, Dict, List

import httpx
import pandas as pd
from fastapi import HTTPException

from app.core.config import BINANCE_BASE_URLS, REQUEST_TIMEOUT_SEC
from app.core.logging import log_event


async def http_get_json(path: str, params: Dict[str, Any]) -> Any:
    timeout = httpx.Timeout(REQUEST_TIMEOUT_SEC)
    last_error = None

    for base_url in BINANCE_BASE_URLS:
        url = f"{base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()

                log_event("binance_request_ok", {
                    "base_url": base_url,
                    "path": path,
                    "params": params,
                    "status_code": resp.status_code,
                })

                return resp.json()

        except Exception as e:
            last_error = e

            log_event("binance_request_failed", {
                "base_url": base_url,
                "path": path,
                "params": params,
                "error": str(e),
            })

    raise HTTPException(
        status_code=502,
        detail=f"All Binance endpoints failed for {path}: {last_error}",
    )


async def fetch_klines(symbol: str, interval: str, limit: int) -> List[List[Any]]:
    return await http_get_json("/api/v3/klines", {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    })


async def fetch_depth(symbol: str, limit: int = 20) -> Dict[str, Any]:
    return await http_get_json("/api/v3/depth", {
        "symbol": symbol,
        "limit": limit,
    })


async def fetch_agg_trades(symbol: str, limit: int = 200) -> List[Dict[str, Any]]:
    return await http_get_json("/api/v3/aggTrades", {
        "symbol": symbol,
        "limit": limit,
    })


def klines_to_df(klines: List[List[Any]]) -> pd.DataFrame:
    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_volume", "taker_buy_quote_volume", "ignore",
    ]

    df = pd.DataFrame(klines, columns=cols)

    if df.empty:
        return df

    numeric_cols = [
        "open", "high", "low", "close", "volume",
        "quote_asset_volume", "number_of_trades",
        "taker_buy_base_volume", "taker_buy_quote_volume",
    ]

    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

    df["taker_sell_base_volume"] = df["volume"] - df["taker_buy_base_volume"]
    df["delta_volume"] = df["taker_buy_base_volume"] - df["taker_sell_base_volume"]
    df["returns"] = df["close"].pct_change().fillna(0.0)
    df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3.0

    return df