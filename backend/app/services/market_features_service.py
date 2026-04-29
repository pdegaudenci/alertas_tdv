"""
Servicio de features de mercado.

Este archivo conserva la lógica original de index.py para:
- indicadores técnicos
- VWAP de sesión
- features de vela
- swings / estructura
- order book / microestructura
- aggTrades / flujo
- recolección paralela de datos de Binance
- extracción de últimas features

No se cambia comportamiento. Solo se separa el código en un módulo.
"""

from typing import Any, Dict, List, Tuple

import asyncio
import numpy as np
import pandas as pd

from app.services.binance_service import (
    fetch_klines,
    fetch_depth,
    fetch_agg_trades,
    klines_to_df,
)
from app.utils.math_utils import safe_float


# ============================================================
# TECHNICALS
# ============================================================

def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

    return tr.rolling(length).mean()


def adx_di(df: pd.DataFrame, length: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    up_move = df["high"].diff()
    down_move = -df["low"].diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    prev_close = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr_sum = tr.rolling(length).sum()

    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(length).sum() / atr_sum.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(length).sum() / atr_sum.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_series = dx.rolling(length).mean()

    return plus_di.fillna(0.0), minus_di.fillna(0.0), adx_series.fillna(0.0)


def compute_session_vwap(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)

    session_date = df["open_time"].dt.date
    out = []
    cum_pv = 0.0
    cum_vol = 0.0
    last_date = None

    for _, row in df.iterrows():
        current_date = row["open_time"].date()

        if current_date != last_date:
            cum_pv = 0.0
            cum_vol = 0.0
            last_date = current_date

        tp = (row["high"] + row["low"] + row["close"]) / 3.0
        vol = float(row["volume"])

        cum_pv += tp * vol
        cum_vol += vol

        out.append(cum_pv / cum_vol if cum_vol > 0 else row["close"])

    return pd.Series(out, index=df.index, dtype=float)


def compute_candle_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["atr14"] = atr(out, 14)
    out["ema20"] = ema(out["close"], 20)
    out["ema50"] = ema(out["close"], 50)
    out["ema200"] = ema(out["close"], 200)

    out["ema20_slope"] = out["ema20"].diff()
    out["ema50_slope"] = out["ema50"].diff()

    out["body_abs"] = (out["close"] - out["open"]).abs()
    out["range_abs"] = (out["high"] - out["low"]).replace(0, np.nan)
    out["body_pct"] = (out["body_abs"] / out["range_abs"]).fillna(0.0)

    out["upper_wick"] = out["high"] - out[["open", "close"]].max(axis=1)
    out["lower_wick"] = out[["open", "close"]].min(axis=1) - out["low"]

    out["upper_wick_pct"] = (out["upper_wick"] / out["range_abs"]).fillna(0.0)
    out["lower_wick_pct"] = (out["lower_wick"] / out["range_abs"]).fillna(0.0)

    out["rvol20"] = out["volume"] / out["volume"].rolling(20).mean().replace(0, np.nan)
    out["trade_count_rvol20"] = out["number_of_trades"] / out["number_of_trades"].rolling(20).mean().replace(0, np.nan)

    out["delta_ma20"] = out["delta_volume"].rolling(20).mean()
    out["impulse_atr"] = (out["body_abs"] / out["atr14"].replace(0, np.nan)).fillna(0.0)
    out["compression_ratio"] = out["atr14"] / out["atr14"].rolling(20).mean().replace(0, np.nan)

    out["vwap_session"] = compute_session_vwap(out)
    out["dist_to_vwap_pct"] = ((out["close"] - out["vwap_session"]) / out["vwap_session"].replace(0, np.nan)) * 100.0

    plus_di, minus_di, adx_series = adx_di(out, 14)
    out["plus_di"] = plus_di
    out["minus_di"] = minus_di
    out["adx"] = adx_series

    return out


# ============================================================
# STRUCTURE / SWINGS
# ============================================================

def detect_swings(df: pd.DataFrame, lookback: int = 5) -> Dict[str, Any]:
    if df.empty or len(df) < (lookback * 2 + 5):
        return {
            "last_swing_high": None,
            "last_swing_low": None,
            "distance_to_swing_high_pct": None,
            "distance_to_swing_low_pct": None,
            "range_mode": False,
            "compression_box": False,
        }

    high = df["high"]
    low = df["low"]

    swing_high_idx = []
    swing_low_idx = []

    for i in range(lookback, len(df) - lookback):
        if high.iloc[i] >= high.iloc[i - lookback:i + lookback + 1].max():
            swing_high_idx.append(i)

        if low.iloc[i] <= low.iloc[i - lookback:i + lookback + 1].min():
            swing_low_idx.append(i)

    last_close = float(df["close"].iloc[-1])

    last_swing_high = float(high.iloc[swing_high_idx[-1]]) if swing_high_idx else None
    last_swing_low = float(low.iloc[swing_low_idx[-1]]) if swing_low_idx else None

    dist_high = ((last_swing_high - last_close) / last_close * 100.0) if last_swing_high else None
    dist_low = ((last_close - last_swing_low) / last_close * 100.0) if last_swing_low else None

    recent = df.tail(20).copy()
    recent_range = float(recent["high"].max() - recent["low"].min())
    recent_atr = float(recent["atr14"].iloc[-1]) if "atr14" in recent.columns else 0.0

    range_mode = recent_atr > 0 and recent_range < (recent_atr * 3.0)
    compression_box = float(recent["compression_ratio"].iloc[-1]) < 0.90 if "compression_ratio" in recent.columns else False

    return {
        "last_swing_high": last_swing_high,
        "last_swing_low": last_swing_low,
        "distance_to_swing_high_pct": dist_high,
        "distance_to_swing_low_pct": dist_low,
        "range_mode": bool(range_mode),
        "compression_box": bool(compression_box),
    }


# ============================================================
# ORDER BOOK / MICROSTRUCTURE
# ============================================================

def analyze_order_book(depth: Dict[str, Any]) -> Dict[str, Any]:
    bids_raw = depth.get("bids", []) or []
    asks_raw = depth.get("asks", []) or []

    bids = [(safe_float(p), safe_float(q)) for p, q in bids_raw if len([p, q]) == 2]
    asks = [(safe_float(p), safe_float(q)) for p, q in asks_raw if len([p, q]) == 2]

    if not bids or not asks:
        return {
            "best_bid": None,
            "best_ask": None,
            "mid_price": None,
            "spread_abs": None,
            "spread_bps": None,
            "bid_notional_top": 0.0,
            "ask_notional_top": 0.0,
            "book_imbalance": 0.0,
            "bid_pressure": 0.0,
            "ask_pressure": 0.0,
            "bid_wall_detected": False,
            "ask_wall_detected": False,
            "vacuum_above": False,
            "vacuum_below": False,
        }

    best_bid = bids[0][0]
    best_ask = asks[0][0]

    mid = (best_bid + best_ask) / 2.0 if (best_bid and best_ask) else 0.0
    spread_abs = max(best_ask - best_bid, 0.0)
    spread_bps = (spread_abs / mid * 10000.0) if mid > 0 else 0.0

    bid_notional = sum(price * qty for price, qty in bids[:10])
    ask_notional = sum(price * qty for price, qty in asks[:10])
    total = bid_notional + ask_notional
    imbalance = ((bid_notional - ask_notional) / total) if total > 0 else 0.0

    bid_sizes = np.array([qty for _, qty in bids[:10]], dtype=float)
    ask_sizes = np.array([qty for _, qty in asks[:10]], dtype=float)

    bid_wall_detected = bool(len(bid_sizes) > 2 and bid_sizes.max() > (bid_sizes.mean() + 2 * bid_sizes.std()))
    ask_wall_detected = bool(len(ask_sizes) > 2 and ask_sizes.max() > (ask_sizes.mean() + 2 * ask_sizes.std()))

    bid_prices = np.array([p for p, _ in bids[:10]], dtype=float)
    ask_prices = np.array([p for p, _ in asks[:10]], dtype=float)

    vacuum_below = False
    vacuum_above = False

    if len(bid_prices) > 3:
        bid_steps = np.abs(np.diff(bid_prices))
        vacuum_below = bool(bid_steps.max() > max(np.median(bid_steps) * 3, 1e-12))

    if len(ask_prices) > 3:
        ask_steps = np.abs(np.diff(ask_prices))
        vacuum_above = bool(ask_steps.max() > max(np.median(ask_steps) * 3, 1e-12))

    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid,
        "spread_abs": spread_abs,
        "spread_bps": spread_bps,
        "bid_notional_top": bid_notional,
        "ask_notional_top": ask_notional,
        "book_imbalance": imbalance,
        "bid_pressure": max(imbalance, 0.0),
        "ask_pressure": max(-imbalance, 0.0),
        "bid_wall_detected": bid_wall_detected,
        "ask_wall_detected": ask_wall_detected,
        "vacuum_above": vacuum_above,
        "vacuum_below": vacuum_below,
    }


def analyze_agg_trades(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {
            "buy_qty": 0.0,
            "sell_qty": 0.0,
            "delta_qty": 0.0,
            "buy_aggression": 0.0,
            "sell_aggression": 0.0,
            "trade_count": 0,
            "vwap_trades": None,
        }

    buy_qty = 0.0
    sell_qty = 0.0
    notional = 0.0
    qty_total = 0.0

    for t in trades:
        qty = safe_float(t.get("q"))
        price = safe_float(t.get("p"))
        buyer_is_maker = bool(t.get("m", False))

        if buyer_is_maker:
            sell_qty += qty
        else:
            buy_qty += qty

        qty_total += qty
        notional += price * qty

    delta_qty = buy_qty - sell_qty
    total = buy_qty + sell_qty

    buy_aggr = buy_qty / total if total > 0 else 0.5
    sell_aggr = sell_qty / total if total > 0 else 0.5
    vwap_trades = notional / qty_total if qty_total > 0 else None

    return {
        "buy_qty": buy_qty,
        "sell_qty": sell_qty,
        "delta_qty": delta_qty,
        "buy_aggression": buy_aggr,
        "sell_aggression": sell_aggr,
        "trade_count": len(trades),
        "vwap_trades": vwap_trades,
    }


# ============================================================
# MARKET VALIDATION ORCHESTRATOR
# ============================================================

async def collect_market_data(symbol: str) -> Dict[str, Any]:
    klines_1m_task = fetch_klines(symbol, "1m", 500)
    klines_5m_task = fetch_klines(symbol, "5m", 200)
    depth_task = fetch_depth(symbol, 20)
    agg_task = fetch_agg_trades(symbol, 200)

    k1, k5, depth, agg = await asyncio.gather(
        klines_1m_task,
        klines_5m_task,
        depth_task,
        agg_task,
    )

    df1 = compute_candle_features(klines_to_df(k1))
    df5 = compute_candle_features(klines_to_df(k5))
    book = analyze_order_book(depth)
    flow = analyze_agg_trades(agg)

    return {
        "df1": df1,
        "df5": df5,
        "depth": depth,
        "order_book": book,
        "agg_trades": agg,
        "flow": flow,
    }


def extract_latest_features(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {
            "close": 0.0,
            "ema20": 0.0,
            "ema50": 0.0,
            "ema200": 0.0,
            "ema20_slope": 0.0,
            "ema50_slope": 0.0,
            "atr14": 0.0,
            "body_pct": 0.0,
            "upper_wick_pct": 0.0,
            "lower_wick_pct": 0.0,
            "rvol20": 1.0,
            "trade_count_rvol20": 1.0,
            "impulse_atr": 0.0,
            "compression_ratio": 1.0,
            "vwap_session": 0.0,
            "dist_to_vwap_pct": 0.0,
            "plus_di": 0.0,
            "minus_di": 0.0,
            "adx": 0.0,
            "ret_mean_20": 0.0,
            "ret_std_20": 0.001,
        }

    row = df.iloc[-1]
    rets20 = df["returns"].tail(20)

    return {
        "close": safe_float(row["close"]),
        "ema20": safe_float(row["ema20"]),
        "ema50": safe_float(row["ema50"]),
        "ema200": safe_float(row["ema200"]),
        "ema20_slope": safe_float(row["ema20_slope"]),
        "ema50_slope": safe_float(row["ema50_slope"]),
        "atr14": safe_float(row["atr14"]),
        "body_pct": safe_float(row["body_pct"]),
        "upper_wick_pct": safe_float(row["upper_wick_pct"]),
        "lower_wick_pct": safe_float(row["lower_wick_pct"]),
        "rvol20": safe_float(row["rvol20"], 1.0),
        "trade_count_rvol20": safe_float(row["trade_count_rvol20"], 1.0),
        "impulse_atr": safe_float(row["impulse_atr"]),
        "compression_ratio": safe_float(row["compression_ratio"], 1.0),
        "vwap_session": safe_float(row["vwap_session"]),
        "dist_to_vwap_pct": safe_float(row["dist_to_vwap_pct"]),
        "plus_di": safe_float(row["plus_di"]),
        "minus_di": safe_float(row["minus_di"]),
        "adx": safe_float(row["adx"]),
        "ret_mean_20": safe_float(rets20.mean(), 0.0),
        "ret_std_20": max(safe_float(rets20.std(), 0.001), 1e-6),
    }