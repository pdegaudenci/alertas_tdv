from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
import os
import json
import math
import asyncio

import httpx
import numpy as np
import pandas as pd
from scipy.special import expit

# ============================================================
# APP
# ============================================================
app = FastAPI(title="TradingView Validation Layer", version="1.0.0")

# ============================================================
# CORS - Streamlit / dashboards
# ============================================================
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
if not allowed_origins:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# GLOBAL STATE
# ============================================================
LAST_ALERT: Dict[str, Any] = {
    "ok": False,
    "message": "No alerts received yet"
}
ALERT_HISTORY = deque(maxlen=200)
LAST_VALIDATION = {
    "ok": False,
    "message": "No validations yet"
}
# ============================================================
# CONFIG
# ============================================================
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")
WEBHOOK_SECRET_ENV = os.getenv("WEBHOOK_SECRET", "")
VALIDATION_THRESHOLD = float(os.getenv("VALIDATION_THRESHOLD", "0.62"))  # probability threshold
MIN_SCORE_THRESHOLD = float(os.getenv("MIN_SCORE_THRESHOLD", "55"))      # score threshold
REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "8.0"))

# Optional ML hook
SKLEARN_MODEL = None
SKLEARN_FEATURE_ORDER: List[str] = []
try:
    import joblib  # type: ignore
    model_path = os.getenv("ML_MODEL_PATH", "").strip()
    feat_path = os.getenv("ML_FEATURES_JSON", "").strip()
    if model_path and os.path.exists(model_path):
        SKLEARN_MODEL = joblib.load(model_path)
    if feat_path and os.path.exists(feat_path):
        with open(feat_path, "r", encoding="utf-8") as fh:
            SKLEARN_FEATURE_ORDER = json.load(fh)
except Exception:
    SKLEARN_MODEL = None
    SKLEARN_FEATURE_ORDER = []

# ============================================================
# UTILS
# ============================================================
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def parse_payload(raw_body: bytes) -> dict:
    text_body = raw_body.decode("utf-8", errors="replace").strip()
    if not text_body:
        return {}
    try:
        parsed = json.loads(text_body)
        if isinstance(parsed, dict):
            return parsed
        return {"raw_json": parsed}
    except json.JSONDecodeError:
        return {"raw_message": text_body}

def validate_secret(x_webhook_secret: Optional[str]) -> None:
    if WEBHOOK_SECRET_ENV and x_webhook_secret != WEBHOOK_SECRET_ENV:
        raise HTTPException(status_code=401, detail="Unauthorized webhook secret")

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default

def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default

def clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))

def pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a / b) * 100.0

def sign_for_side(side: str) -> int:
    return 1 if str(side).lower() == "long" else -1

def nested_get(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default

def build_log(route: str, payload: dict, headers: dict | None = None) -> dict:
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    quality = payload.get("quality", {}) if isinstance(payload.get("quality"), dict) else {}

    return {
        "received_at": utc_now_iso(),
        "route": route,
        "schema_version": payload.get("schema_version"),
        "message_type": payload.get("message_type"),
        "symbol": signal.get("symbol") or payload.get("symbol") or payload.get("ticker"),
        "timeframe": signal.get("tf") or payload.get("timeframe") or payload.get("tf"),
        "event": signal.get("event") or payload.get("event"),
        "side": signal.get("side") or payload.get("side"),
        "setup": signal.get("setup") or payload.get("setup"),
        "price": signal.get("price") or payload.get("price"),
        "phase": context.get("phase") or payload.get("phase"),
        "regime": context.get("regime"),
        "quality_score": quality.get("quality_score") or payload.get("quality_score") or payload.get("score"),
        "headers": headers or {},
    }

# ============================================================
# ALERT NORMALIZATION
# ============================================================
def normalize_alert(payload: Dict[str, Any]) -> Dict[str, Any]:
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    movement = payload.get("movement", {}) if isinstance(payload.get("movement"), dict) else {}
    liquidity = payload.get("liquidity", {}) if isinstance(payload.get("liquidity"), dict) else {}
    structure = payload.get("structure", {}) if isinstance(payload.get("structure"), dict) else {}
    trigger = payload.get("trigger", {}) if isinstance(payload.get("trigger"), dict) else {}
    quality = payload.get("quality", {}) if isinstance(payload.get("quality"), dict) else {}
    trade_plan = payload.get("trade_plan", {}) if isinstance(payload.get("trade_plan"), dict) else {}
    setup_timing = payload.get("setup_timing", {}) if isinstance(payload.get("setup_timing"), dict) else {}
    setup_validation = payload.get("setup_validation", {}) if isinstance(payload.get("setup_validation"), dict) else {}
    setup_context = payload.get("setup_context", {}) if isinstance(payload.get("setup_context"), dict) else {}
    sequence = payload.get("sequence", {}) if isinstance(payload.get("sequence"), dict) else {}
    htf_context = payload.get("htf_context", {}) if isinstance(payload.get("htf_context"), dict) else {}

    side = str(signal.get("side") or payload.get("side") or "").lower().strip()
    symbol = str(signal.get("symbol") or payload.get("symbol") or payload.get("ticker") or "BTCUSDC").upper().strip()
    event = str(signal.get("event") or payload.get("event") or "").upper().strip()
    tf = str(signal.get("tf") or payload.get("tf") or payload.get("timeframe") or "1m").strip()

    entry_price = safe_float(signal.get("price") or signal.get("close") or payload.get("price"))
    tp_price = safe_float(trade_plan.get("tp_price"))
    sl_price = safe_float(trade_plan.get("sl_price"))

    if side not in {"long", "short"}:
        if "LONG" in event:
            side = "long"
        elif "SHORT" in event:
            side = "short"

    normalized = {
        "schema_version": payload.get("schema_version", "unknown"),
        "message_type": payload.get("message_type", "unknown"),
        "source": payload.get("source", {}),
        "signal": signal,
        "context": context,
        "movement": movement,
        "liquidity": liquidity,
        "structure": structure,
        "trigger": trigger,
        "quality": quality,
        "trade_plan": trade_plan,
        "setup_timing": setup_timing,
        "setup_validation": setup_validation,
        "setup_context": setup_context,
        "sequence": sequence,
        "htf_context": htf_context,

        "symbol": symbol,
        "side": side,
        "event": event,
        "tf": tf,
        "entry_price": entry_price,
        "tp_price": tp_price,
        "sl_price": sl_price,

        # Reusable Pine outputs
        "quality_score_alert": safe_float(quality.get("quality_score") or payload.get("quality_score")),
        "quality_class_alert": quality.get("quality_class"),
        "quality_approved_alert": bool(quality.get("quality_approved", False)),
        "regime": context.get("regime"),
        "phase": context.get("phase"),
        "dir_state": context.get("dir_state"),
        "raw_dir_state": context.get("raw_dir_state"),
        "phase_strength": safe_float(context.get("phase_strength")),
        "regime_strength": safe_float(context.get("regime_strength")),
        "mov_state": movement.get("mov_state"),
        "adx_alert": safe_float(movement.get("adx")),
        "plus_di_alert": safe_float(movement.get("plus_di")),
        "minus_di_alert": safe_float(movement.get("minus_di")),
        "atr_alert": safe_float(movement.get("atr")),
        "body_pct_alert": safe_float(movement.get("body_pct")),
        "ema_slope_alert": safe_float(movement.get("ema_slope")),
        "ema_spread_atr_alert": safe_float(movement.get("ema_spread_atr")),
        "impulse_alert": safe_float(movement.get("impulse")),
        "efficiency_local_alert": safe_float(movement.get("efficiency_local")),
        "efficiency_global_alert": safe_float(movement.get("efficiency_global")),
        "too_extended_warn_alert": bool(quality.get("too_extended_warn") or movement.get("too_extended_long_warn") or movement.get("too_extended_short_warn")),
        "too_extended_block_alert": bool(quality.get("too_extended_block") or movement.get("too_extended_long_block") or movement.get("too_extended_short_block")),
        "late_trend_alert": bool(quality.get("late_trend") or movement.get("late_long_trend") or movement.get("late_short_trend")),
        "liq_state": liquidity.get("liq_state"),
        "sweep_high": bool(liquidity.get("sweep_high", False)),
        "sweep_low": bool(liquidity.get("sweep_low", False)),
        "absorb_bull": bool(liquidity.get("absorb_bull", False)),
        "absorb_bear": bool(liquidity.get("absorb_bear", False)),
        "bars_since_sweep_low": safe_int(liquidity.get("bars_since_sweep_low"), 999),
        "bars_since_sweep_high": safe_int(liquidity.get("bars_since_sweep_high"), 999),
        "trigger_alignment": safe_float(trigger.get("trigger_alignment")),
        "trigger_long": bool(trigger.get("trigger_long", False)),
        "trigger_short": bool(trigger.get("trigger_short", False)),
        "ast_dir": trigger.get("ast_dir"),
        "hull_bull": bool(trigger.get("hull_bull", False)),
        "hull_bear": bool(trigger.get("hull_bear", False)),
        "ast_bull": bool(trigger.get("ast_bull", False)),
        "ast_bear": bool(trigger.get("ast_bear", False)),
        "trigger_age_bars": safe_int(trigger.get("trigger_age_bars"), 999),
        "htf_tf": htf_context.get("htf_tf"),
        "htf_phase": htf_context.get("htf_phase"),
        "htf_phase_strength": safe_float(htf_context.get("htf_phase_strength")),
        "htf_phase_bias": htf_context.get("htf_phase_bias"),
        "htf_adx": safe_float(htf_context.get("htf_adx")),
        "rr_ratio_alert": safe_float(trade_plan.get("rr_ratio")),
        "distance_to_tp_pct_alert": safe_float(trade_plan.get("distance_to_tp_pct")),
        "distance_to_sl_pct_alert": safe_float(trade_plan.get("distance_to_sl_pct")),
        "tp_perc_alert": safe_float(trade_plan.get("tp_perc")),
        "sl_perc_alert": safe_float(trade_plan.get("sl_perc")),
    }
    return normalized

# ============================================================
# BINANCE CLIENT
# ============================================================
async def http_get_json(url: str, params: Dict[str, Any]) -> Any:
    timeout = httpx.Timeout(REQUEST_TIMEOUT_SEC)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

async def fetch_klines(symbol: str, interval: str, limit: int) -> List[List[Any]]:
    url = f"{BINANCE_BASE_URL}/api/v3/klines"
    return await http_get_json(url, {"symbol": symbol, "interval": interval, "limit": limit})

async def fetch_depth(symbol: str, limit: int = 20) -> Dict[str, Any]:
    url = f"{BINANCE_BASE_URL}/api/v3/depth"
    return await http_get_json(url, {"symbol": symbol, "limit": limit})

async def fetch_agg_trades(symbol: str, limit: int = 200) -> List[Dict[str, Any]]:
    url = f"{BINANCE_BASE_URL}/api/v3/aggTrades"
    return await http_get_json(url, {"symbol": symbol, "limit": limit})

def klines_to_df(klines: List[List[Any]]) -> pd.DataFrame:
    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
    ]
    df = pd.DataFrame(klines, columns=cols)
    if df.empty:
        return df

    numeric_cols = [
        "open", "high", "low", "close", "volume",
        "quote_asset_volume", "number_of_trades",
        "taker_buy_base_volume", "taker_buy_quote_volume"
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
        (df["low"] - prev_close).abs()
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
        (df["low"] - prev_close).abs()
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

    # Vacuum: gap between consecutive levels above typical step
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
        # buyer_is_maker=True => passive buyer, aggressive sell side
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
# PROBABILITY TP BEFORE SL
# ============================================================
def first_hit_probability_barrier(
    side: str,
    entry_price: float,
    tp_price: float,
    sl_price: float,
    mu_per_bar: float,
    sigma_per_bar: float
) -> float:
    """
    Approximates probability of hitting TP before SL using a drifted Brownian
    first-passage style barrier formula on log returns.

    side=long:
      lower barrier = SL
      upper barrier = TP

    side=short:
      transformed so that 'up' corresponds to profit side as well.
    """
    if entry_price <= 0 or tp_price <= 0 or sl_price <= 0:
        return 0.5

    if sigma_per_bar <= 1e-9:
        sigma_per_bar = 1e-9

    if side == "long":
        a = abs(math.log(entry_price / sl_price)) if sl_price < entry_price else abs((entry_price - sl_price) / entry_price)
        b = abs(math.log(tp_price / entry_price)) if tp_price > entry_price else abs((tp_price - entry_price) / entry_price)
    else:
        # For short, profit barrier is down, stop barrier is up.
        a = abs(math.log(sl_price / entry_price)) if sl_price > entry_price else abs((sl_price - entry_price) / entry_price)
        b = abs(math.log(entry_price / tp_price)) if tp_price < entry_price else abs((entry_price - tp_price) / entry_price)

    if a <= 1e-9 or b <= 1e-9:
        return 0.5

    x = a
    L = a + b
    mu = mu_per_bar
    sigma2 = sigma_per_bar ** 2

    # Driftless fallback
    if abs(mu) < 1e-10:
        p = x / L
        return clip(p, 0.01, 0.99)

    try:
        num = 1.0 - math.exp((-2.0 * mu * x) / sigma2)
        den = 1.0 - math.exp((-2.0 * mu * L) / sigma2)
        if abs(den) < 1e-12:
            return clip(x / L, 0.01, 0.99)
        p = num / den
        return clip(p, 0.01, 0.99)
    except OverflowError:
        return clip(x / L, 0.01, 0.99)

def build_feature_vector_for_model(features: Dict[str, float]) -> Optional[np.ndarray]:
    if SKLEARN_MODEL is None or not SKLEARN_FEATURE_ORDER:
        return None
    vector = []
    for feat in SKLEARN_FEATURE_ORDER:
        vector.append(float(features.get(feat, 0.0)))
    return np.array(vector, dtype=float).reshape(1, -1)

def estimate_tp_before_sl_probability(
    normalized_alert: Dict[str, Any],
    backend_features: Dict[str, float],
    score_external: float
) -> Dict[str, Any]:
    side = normalized_alert["side"]
    entry_price = safe_float(normalized_alert["entry_price"])
    tp_price = safe_float(normalized_alert["tp_price"])
    sl_price = safe_float(normalized_alert["sl_price"])

    last_close = backend_features.get("close", entry_price)
    if entry_price <= 0:
        entry_price = last_close

    if tp_price <= 0 or sl_price <= 0:
        tp_pct = safe_float(normalized_alert.get("tp_perc_alert"), 0.0)
        sl_pct = safe_float(normalized_alert.get("sl_perc_alert"), 0.0)
        if tp_pct > 0 and sl_pct > 0 and entry_price > 0:
            tp_ratio = tp_pct / 100.0 if tp_pct > 1 else tp_pct
            sl_ratio = sl_pct / 100.0 if sl_pct > 1 else sl_pct
            if side == "long":
                tp_price = entry_price * (1.0 + tp_ratio)
                sl_price = entry_price * (1.0 - sl_ratio)
            else:
                tp_price = entry_price * (1.0 - tp_ratio)
                sl_price = entry_price * (1.0 + sl_ratio)

    if side not in {"long", "short"}:
        return {
            "probability_tp_before_sl": 0.5,
            "probability_model": "unknown_side",
            "barrier_component": 0.5,
            "technical_component": 0.5,
            "ml_component": None,
        }

    # Drift from technical state + signed short-term return tendency
    signed = sign_for_side(side)
    ret_mean = backend_features.get("ret_mean_20", 0.0) * signed
    ema_alignment = backend_features.get("ema_alignment_score", 0.0) * 0.0015
    flow_alignment = backend_features.get("flow_alignment_score", 0.0) * 0.0012
    book_alignment = backend_features.get("book_alignment_score", 0.0) * 0.0018
    vwap_alignment = backend_features.get("vwap_alignment_score", 0.0) * 0.0010
    adx_bonus = max(backend_features.get("adx", 0.0) - 18.0, 0.0) * 0.0002 * (1 if backend_features.get("trend_aligned", 0.0) > 0 else -0.3)

    mu_per_bar = ret_mean + ema_alignment + flow_alignment + book_alignment + vwap_alignment + adx_bonus
    sigma_per_bar = max(backend_features.get("ret_std_20", 0.0), 1e-6)

    barrier_prob = first_hit_probability_barrier(
        side=side,
        entry_price=entry_price,
        tp_price=tp_price,
        sl_price=sl_price,
        mu_per_bar=mu_per_bar,
        sigma_per_bar=sigma_per_bar
    )

    # Technical probability from score + alert state
    quality_alert = safe_float(normalized_alert.get("quality_score_alert"), 50.0)
    trigger_alignment = safe_float(normalized_alert.get("trigger_alignment"), 0.0)
    htf_strength = safe_float(normalized_alert.get("htf_phase_strength"), 0.0)
    ext_penalty = 8.0 if normalized_alert.get("too_extended_block_alert") else (4.0 if normalized_alert.get("too_extended_warn_alert") else 0.0)
    late_penalty = 4.0 if normalized_alert.get("late_trend_alert") else 0.0

    technical_raw = (
        (0.55 * score_external) +
        (0.25 * quality_alert) +
        (0.10 * trigger_alignment) +
        (0.10 * htf_strength) -
        ext_penalty -
        late_penalty
    )
    technical_prob = float(expit((technical_raw - 60.0) / 7.5))

    ml_component = None
    probability_model = "hybrid_barrier_logit"

    if SKLEARN_MODEL is not None and SKLEARN_FEATURE_ORDER:
        try:
            model_vector = build_feature_vector_for_model(backend_features)
            if model_vector is not None and hasattr(SKLEARN_MODEL, "predict_proba"):
                ml_component = float(SKLEARN_MODEL.predict_proba(model_vector)[0][1])
                probability_model = "hybrid_barrier_logit_sklearn"
        except Exception:
            ml_component = None

    if ml_component is not None:
        final_prob = (0.40 * barrier_prob) + (0.25 * technical_prob) + (0.35 * ml_component)
    else:
        final_prob = (0.55 * barrier_prob) + (0.45 * technical_prob)

    final_prob = clip(final_prob, 0.01, 0.99)

    return {
        "probability_tp_before_sl": final_prob,
        "probability_model": probability_model,
        "barrier_component": barrier_prob,
        "technical_component": technical_prob,
        "ml_component": ml_component,
        "mu_per_bar": mu_per_bar,
        "sigma_per_bar": sigma_per_bar,
        "tp_price_used": tp_price,
        "sl_price_used": sl_price,
    }

# ============================================================
# SCORING
# ============================================================
def compute_external_scores(
    normalized_alert: Dict[str, Any],
    f1: Dict[str, float],
    f5: Dict[str, float],
    order_book: Dict[str, Any],
    flow: Dict[str, Any],
    structure: Dict[str, Any]
) -> Dict[str, Any]:
    side = normalized_alert["side"]
    signed = sign_for_side(side)
    reasons: List[str] = []
    penalties: List[str] = []
    score = 50.0  # neutral starting point

    # Trigger / signal from alert
    if side == "long" and normalized_alert.get("trigger_long"):
        score += 8
        reasons.append("trigger_long_alert")
    if side == "short" and normalized_alert.get("trigger_short"):
        score += 8
        reasons.append("trigger_short_alert")

    if safe_float(normalized_alert.get("trigger_alignment")) >= 70:
        score += 7
        reasons.append("strong_trigger_alignment")
    elif safe_float(normalized_alert.get("trigger_alignment")) >= 50:
        score += 4
        reasons.append("acceptable_trigger_alignment")

    # Quality from alert
    quality_alert = safe_float(normalized_alert.get("quality_score_alert"), 50)
    if quality_alert >= 80:
        score += 10
        reasons.append("high_alert_quality")
    elif quality_alert >= 65:
        score += 6
        reasons.append("good_alert_quality")
    elif quality_alert < 45:
        score -= 8
        penalties.append("weak_alert_quality")

    # HTF / context
    htf_phase = str(normalized_alert.get("htf_phase") or "").upper()
    htf_bias = str(normalized_alert.get("htf_phase_bias") or "").upper()
    htf_strength = safe_float(normalized_alert.get("htf_phase_strength"))

    if side == "long" and ("BULL" in htf_phase or "UP" in htf_bias):
        score += 9
        reasons.append("htf_aligned")
    elif side == "short" and ("BEAR" in htf_phase or "DOWN" in htf_bias):
        score += 9
        reasons.append("htf_aligned")
    elif htf_phase or htf_bias:
        score -= 9
        penalties.append("htf_opposite")

    if htf_strength >= 70:
        score += 4
        reasons.append("htf_strength_high")

    # Trend and EMA alignment backend 1m/5m
    ema20 = f1["ema20"]
    ema50 = f1["ema50"]
    ema200 = f1["ema200"]
    close = f1["close"]

    long_trend_ok = (close > ema20 > ema50) and (ema20 > ema200 or close > ema200)
    short_trend_ok = (close < ema20 < ema50) and (ema20 < ema200 or close < ema200)

    trend_aligned = 0.0
    if side == "long" and long_trend_ok:
        score += 10
        reasons.append("ema_trend_aligned")
        trend_aligned = 1.0
    elif side == "short" and short_trend_ok:
        score += 10
        reasons.append("ema_trend_aligned")
        trend_aligned = 1.0
    else:
        score -= 8
        penalties.append("ema_trend_not_aligned")

    if f1["adx"] >= 22:
        score += 5
        reasons.append("adx_supportive")
    elif f1["adx"] < 14:
        score -= 5
        penalties.append("low_adx")

    if side == "long" and f1["plus_di"] > f1["minus_di"]:
        score += 4
        reasons.append("di_supportive")
    elif side == "short" and f1["minus_di"] > f1["plus_di"]:
        score += 4
        reasons.append("di_supportive")
    else:
        score -= 3
        penalties.append("di_not_supportive")

    # VWAP
    if side == "long" and close >= f1["vwap_session"]:
        score += 4
        reasons.append("price_above_vwap")
    elif side == "short" and close <= f1["vwap_session"]:
        score += 4
        reasons.append("price_below_vwap")
    else:
        score -= 3
        penalties.append("vwap_misaligned")

    # Volume / flow
    if f1["rvol20"] >= 1.20:
        score += 6
        reasons.append("rvol_strong")
    elif f1["rvol20"] < 0.80:
        score -= 6
        penalties.append("rvol_weak")

    if side == "long" and flow["delta_qty"] > 0:
        score += 6
        reasons.append("buy_flow_positive")
    elif side == "short" and flow["delta_qty"] < 0:
        score += 6
        reasons.append("sell_flow_positive")
    else:
        score -= 5
        penalties.append("flow_not_supportive")

    # Order book
    if order_book["spread_bps"] is not None:
        if order_book["spread_bps"] <= 1.5:
            score += 5
            reasons.append("spread_low")
        elif order_book["spread_bps"] > 4.0:
            score -= 10
            penalties.append("spread_high")

    if side == "long" and order_book["book_imbalance"] > 0.08:
        score += 7
        reasons.append("bullish_book_imbalance")
    elif side == "short" and order_book["book_imbalance"] < -0.08:
        score += 7
        reasons.append("bearish_book_imbalance")
    else:
        score -= 4
        penalties.append("book_imbalance_not_supportive")

    if side == "long" and order_book["ask_wall_detected"]:
        score -= 6
        penalties.append("ask_wall_nearby")
    if side == "short" and order_book["bid_wall_detected"]:
        score -= 6
        penalties.append("bid_wall_nearby")

    # Liquidity from alert
    if side == "long" and normalized_alert.get("sweep_low") and normalized_alert.get("bars_since_sweep_low", 999) <= 6:
        score += 6
        reasons.append("fresh_sweep_low")
    if side == "short" and normalized_alert.get("sweep_high") and normalized_alert.get("bars_since_sweep_high", 999) <= 6:
        score += 6
        reasons.append("fresh_sweep_high")

    if side == "long" and normalized_alert.get("absorb_bull"):
        score += 4
        reasons.append("bull_absorption_alert")
    if side == "short" and normalized_alert.get("absorb_bear"):
        score += 4
        reasons.append("bear_absorption_alert")

    # Extension / lateness
    if normalized_alert.get("too_extended_block_alert"):
        score -= 15
        penalties.append("too_extended_block")
    elif normalized_alert.get("too_extended_warn_alert"):
        score -= 7
        penalties.append("too_extended_warn")

    if normalized_alert.get("late_trend_alert"):
        score -= 7
        penalties.append("late_trend")

    # Structure / TP room
    tp_room_ok = False
    if side == "long":
        dist_high = structure.get("distance_to_swing_high_pct")
        if dist_high is None or dist_high >= max(safe_float(normalized_alert.get("distance_to_tp_pct_alert"), 0.20) * 1.10, 0.18):
            score += 5
            reasons.append("tp_room_ok")
            tp_room_ok = True
        else:
            score -= 8
            penalties.append("resistance_too_close")
    else:
        dist_low = structure.get("distance_to_swing_low_pct")
        if dist_low is None or dist_low >= max(safe_float(normalized_alert.get("distance_to_tp_pct_alert"), 0.20) * 1.10, 0.18):
            score += 5
            reasons.append("tp_room_ok")
            tp_room_ok = True
        else:
            score -= 8
            penalties.append("support_too_close")

    if structure.get("range_mode"):
        score -= 6
        penalties.append("range_mode")
    if structure.get("compression_box"):
        score -= 3
        penalties.append("compression_box")

    score = clip(score, 0, 100)

    ema_alignment_score = 1.0 if trend_aligned > 0 else -1.0
    flow_alignment_score = 1.0 if (
        (side == "long" and flow["delta_qty"] > 0) or
        (side == "short" and flow["delta_qty"] < 0)
    ) else -1.0
    book_alignment_score = 1.0 if (
        (side == "long" and order_book["book_imbalance"] > 0.0) or
        (side == "short" and order_book["book_imbalance"] < 0.0)
    ) else -1.0
    vwap_alignment_score = 1.0 if (
        (side == "long" and close >= f1["vwap_session"]) or
        (side == "short" and close <= f1["vwap_session"])
    ) else -1.0

    backend_feature_pack = {
        "close": f1["close"],
        "ema20": f1["ema20"],
        "ema50": f1["ema50"],
        "ema200": f1["ema200"],
        "adx": f1["adx"],
        "plus_di": f1["plus_di"],
        "minus_di": f1["minus_di"],
        "rvol20": f1["rvol20"],
        "ret_mean_20": f1["ret_mean_20"],
        "ret_std_20": f1["ret_std_20"],
        "spread_bps": order_book["spread_bps"] or 0.0,
        "book_imbalance": order_book["book_imbalance"],
        "delta_qty": flow["delta_qty"],
        "buy_aggression": flow["buy_aggression"],
        "sell_aggression": flow["sell_aggression"],
        "dist_to_vwap_pct": f1["dist_to_vwap_pct"],
        "ema_alignment_score": ema_alignment_score,
        "flow_alignment_score": flow_alignment_score,
        "book_alignment_score": book_alignment_score,
        "vwap_alignment_score": vwap_alignment_score,
        "trend_aligned": trend_aligned,
        "tp_room_ok": 1.0 if tp_room_ok else 0.0,
    }

    return {
        "score_external": score,
        "reasons": reasons,
        "penalties": penalties,
        "backend_feature_pack": backend_feature_pack,
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
        agg_task
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
            "close": 0.0, "ema20": 0.0, "ema50": 0.0, "ema200": 0.0,
            "ema20_slope": 0.0, "ema50_slope": 0.0,
            "atr14": 0.0, "body_pct": 0.0, "upper_wick_pct": 0.0, "lower_wick_pct": 0.0,
            "rvol20": 1.0, "trade_count_rvol20": 1.0,
            "impulse_atr": 0.0, "compression_ratio": 1.0, "vwap_session": 0.0, "dist_to_vwap_pct": 0.0,
            "plus_di": 0.0, "minus_di": 0.0, "adx": 0.0,
            "ret_mean_20": 0.0, "ret_std_20": 0.001
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

async def run_validation(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_alert(payload)

    if normalized["side"] not in {"long", "short"}:
        raise HTTPException(status_code=400, detail="Payload missing valid side (long/short)")
    if not normalized["symbol"]:
        raise HTTPException(status_code=400, detail="Payload missing symbol")

    market = await collect_market_data(normalized["symbol"])
    df1 = market["df1"]
    df5 = market["df5"]

    if df1.empty or df5.empty:
        raise HTTPException(status_code=502, detail="Could not fetch enough market data from Binance")

    f1 = extract_latest_features(df1)
    f5 = extract_latest_features(df5)
    structure = detect_swings(df1, lookback=5)

    ext = compute_external_scores(
        normalized_alert=normalized,
        f1=f1,
        f5=f5,
        order_book=market["order_book"],
        flow=market["flow"],
        structure=structure
    )

    prob = estimate_tp_before_sl_probability(
        normalized_alert=normalized,
        backend_features=ext["backend_feature_pack"],
        score_external=ext["score_external"]
    )

    approve = bool(
        prob["probability_tp_before_sl"] >= VALIDATION_THRESHOLD and
        ext["score_external"] >= MIN_SCORE_THRESHOLD and
        not normalized.get("too_extended_block_alert", False)
    )

    confidence = round(prob["probability_tp_before_sl"] * 100.0, 2)
    entry_price = normalized["entry_price"] if normalized["entry_price"] > 0 else f1["close"]

    validation = {
        "approve": approve,
        "confidence": confidence,
        "side": normalized["side"],
        "symbol": normalized["symbol"],
        "event": normalized["event"],
        "entry_price": entry_price,
        "tp": prob["tp_price_used"],
        "sl": prob["sl_price_used"],
        "rr": safe_float(normalized.get("rr_ratio_alert")),
        "probability_tp_before_sl": round(prob["probability_tp_before_sl"], 4),
        "probability_model": prob["probability_model"],
        "barrier_component": round(prob["barrier_component"], 4),
        "technical_component": round(prob["technical_component"], 4),
        "ml_component": round(prob["ml_component"], 4) if prob["ml_component"] is not None else None,
        "score_external": round(ext["score_external"], 2),
        "quality_score_alert": round(safe_float(normalized.get("quality_score_alert")), 2),
        "reason": ext["reasons"][:12],
        "penalties": ext["penalties"][:12],
        "market_snapshot": {
            "close_1m": round(f1["close"], 4),
            "ema20_1m": round(f1["ema20"], 4),
            "ema50_1m": round(f1["ema50"], 4),
            "ema200_1m": round(f1["ema200"], 4),
            "adx_1m": round(f1["adx"], 2),
            "plus_di_1m": round(f1["plus_di"], 2),
            "minus_di_1m": round(f1["minus_di"], 2),
            "atr14_1m": round(f1["atr14"], 4),
            "rvol20_1m": round(f1["rvol20"], 3),
            "impulse_atr_1m": round(f1["impulse_atr"], 3),
            "dist_to_vwap_pct_1m": round(f1["dist_to_vwap_pct"], 4),
            "spread_bps": round(safe_float(market["order_book"]["spread_bps"]), 4),
            "book_imbalance": round(safe_float(market["order_book"]["book_imbalance"]), 4),
            "buy_aggression": round(safe_float(market["flow"]["buy_aggression"]), 4),
            "sell_aggression": round(safe_float(market["flow"]["sell_aggression"]), 4),
            "delta_qty": round(safe_float(market["flow"]["delta_qty"]), 6),
            "bid_wall_detected": market["order_book"]["bid_wall_detected"],
            "ask_wall_detected": market["order_book"]["ask_wall_detected"],
            "vacuum_above": market["order_book"]["vacuum_above"],
            "vacuum_below": market["order_book"]["vacuum_below"],
        },
        "structure_snapshot": structure,
        "alert_reused": {
            "regime": normalized.get("regime"),
            "phase": normalized.get("phase"),
            "dir_state": normalized.get("dir_state"),
            "mov_state": normalized.get("mov_state"),
            "liq_state": normalized.get("liq_state"),
            "htf_phase": normalized.get("htf_phase"),
            "htf_phase_strength": normalized.get("htf_phase_strength"),
            "trigger_alignment": normalized.get("trigger_alignment"),
            "too_extended_warn_alert": normalized.get("too_extended_warn_alert"),
            "too_extended_block_alert": normalized.get("too_extended_block_alert"),
            "late_trend_alert": normalized.get("late_trend_alert"),
        }
    }

    return {
        "ok": True,
        "validated_at": utc_now_iso(),
        "message": "Validation completed",
        "validation": validation,
        "normalized_alert": {
            "schema_version": normalized["schema_version"],
            "message_type": normalized["message_type"],
            "symbol": normalized["symbol"],
            "side": normalized["side"],
            "event": normalized["event"],
            "tf": normalized["tf"],
            "entry_price": normalized["entry_price"],
            "tp_price_alert": normalized["tp_price"],
            "sl_price_alert": normalized["sl_price"],
            "quality_score_alert": normalized["quality_score_alert"],
            "quality_class_alert": normalized["quality_class_alert"],
        }
    }
def build_history_item(payload: dict, validation_result: dict | None = None) -> dict:
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    quality = payload.get("quality", {}) if isinstance(payload.get("quality"), dict) else {}
    htf_context = payload.get("htf_context", {}) if isinstance(payload.get("htf_context"), dict) else {}

    validation = validation_result.get("validation", {}) if isinstance(validation_result, dict) else {}

    return {
        "received_at": utc_now_iso(),
        "schema_version": payload.get("schema_version"),
        "message_type": payload.get("message_type"),
        "symbol": signal.get("symbol") or payload.get("symbol") or payload.get("ticker"),
        "tf": signal.get("tf") or payload.get("tf") or payload.get("timeframe"),
        "event": signal.get("event") or payload.get("event"),
        "side": signal.get("side") or payload.get("side"),
        "setup": signal.get("setup") or payload.get("setup"),
        "price": signal.get("price") or payload.get("price"),
        "phase": context.get("phase"),
        "regime": context.get("regime"),
        "quality_score": quality.get("quality_score") or payload.get("quality_score") or payload.get("score"),
        "htf_phase": htf_context.get("htf_phase"),
        "htf_phase_strength": htf_context.get("htf_phase_strength"),
        "approve": validation.get("approve"),
        "confidence": validation.get("confidence"),
        "probability_tp_before_sl": validation.get("probability_tp_before_sl"),
        "score_external": validation.get("score_external"),
        "reason": validation.get("reason", []),
        "penalties": validation.get("penalties", []),
        "validation": validation,
        "payload": payload
    }

# ============================================================
# ROUTES
# ============================================================
@app.get("/")
async def healthcheck():
    return {
        "ok": True,
        "service": "tradingview-validation-layer",
        "timestamp": utc_now_iso(),
        "routes": [
            "/",
            "/api/latest",
            "/api/webhook",
            "/api/validate",
            "/api/health/binance"
        ],
        "binance_base_url": BINANCE_BASE_URL,
        "model_loaded": SKLEARN_MODEL is not None,
        "allowed_origins": allowed_origins,
    }
@app.get("/api/alerts")
async def get_alerts(limit: int = 50):
    items = list(ALERT_HISTORY)[-limit:]
    items.reverse()
    return {
        "ok": True,
        "count": len(items),
        "items": items
    }


@app.get("/api/validation/latest")
async def get_latest_validation():
    return LAST_VALIDATION
@app.get("/api/latest")
async def latest_alert():
    return LAST_ALERT

@app.get("/api/health/binance")
async def health_binance():
    try:
        depth = await fetch_depth("BTCUSDC", 5)
        return {
            "ok": True,
            "timestamp": utc_now_iso(),
            "symbol_tested": "BTCUSDC",
            "depth_keys": list(depth.keys()),
        }
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "timestamp": utc_now_iso(),
                "error": str(e),
            },
        )

@app.post("/api/validate")
async def validate_payload(
    request: Request,
    x_webhook_secret: Optional[str] = Header(default=None)
):
    validate_secret(x_webhook_secret)
    raw_body = await request.body()
    payload = parse_payload(raw_body)
    if not payload:
        if LAST_ALERT.get("payload"):
            payload = LAST_ALERT["payload"]
        else:
            raise HTTPException(status_code=400, detail="Empty payload and no LAST_ALERT stored")

    result = await run_validation(payload)
    return JSONResponse(status_code=200, content=result)

@app.post("/api/webhook")
async def tradingview_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(default=None)
):
    global LAST_ALERT, LAST_VALIDATION, ALERT_HISTORY

    validate_secret(x_webhook_secret)

    raw_body = await request.body()
    payload = parse_payload(raw_body)

    log_data = build_log(
        route="/api/webhook",
        payload=payload,
        headers={
            "content_type": request.headers.get("content-type", ""),
            "user_agent": request.headers.get("user-agent", ""),
        },
    )

    print(json.dumps(log_data, ensure_ascii=False))

    validation_result = None
    try:
        validation_result = await run_validation(payload)
        LAST_VALIDATION = validation_result
    except Exception as e:
        validation_result = {
            "ok": False,
            "validated_at": utc_now_iso(),
            "message": "Validation failed",
            "error": str(e)
        }
        LAST_VALIDATION = validation_result

    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    quality = payload.get("quality", {}) if isinstance(payload.get("quality"), dict) else {}
    htf_context = payload.get("htf_context", {}) if isinstance(payload.get("htf_context"), dict) else {}

    LAST_ALERT = {
        "ok": True,
        "received_at": utc_now_iso(),
        "route": "/api/webhook",
        "schema_version": payload.get("schema_version"),
        "message_type": payload.get("message_type"),
        "symbol": signal.get("symbol") or payload.get("symbol") or payload.get("ticker"),
        "timeframe": signal.get("tf") or payload.get("timeframe") or payload.get("tf"),
        "event": signal.get("event") or payload.get("event"),
        "setup": signal.get("setup") or payload.get("setup"),
        "phase": context.get("phase"),
        "regime": context.get("regime"),
        "strength": context.get("phase_strength") or payload.get("strength"),
        "phase_5m": htf_context.get("htf_phase") or payload.get("phase_5m"),
        "strength_5m": htf_context.get("htf_phase_strength") or payload.get("strength_5m"),
        "quality_score": quality.get("quality_score") or payload.get("quality_score") or payload.get("score"),
        "price": signal.get("price") or payload.get("price"),
        "side": signal.get("side") or payload.get("side"),
        "payload": payload,
        "validation": validation_result,
    }

    history_item = build_history_item(payload, validation_result)
    ALERT_HISTORY.append(history_item)

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "message": "Alert received and processed",
            "data": LAST_ALERT,
        },
    )

@app.post("/")
async def root_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(default=None)
):
    return await tradingview_webhook(request=request, x_webhook_secret=x_webhook_secret)
