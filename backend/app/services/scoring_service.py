"""
Servicio de scoring externo.

Este archivo conserva la lógica original de index.py para calcular el score
externo de una señal usando:
- contexto de alerta
- HTF
- EMA / ADX / DI
- VWAP
- volumen
- flujo aggTrades
- order book
- liquidez
- extensión / lateness
- espacio hacia TP

"""

from typing import Any, Dict, List

from app.utils.math_utils import safe_float, sign_for_side, clip


def compute_external_scores(
    normalized_alert: Dict[str, Any],
    f1: Dict[str, float],
    f5: Dict[str, float],
    order_book: Dict[str, Any],
    flow: Dict[str, Any],
    structure: Dict[str, Any],
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
        (side == "long" and flow["delta_qty"] > 0)
        or (side == "short" and flow["delta_qty"] < 0)
    ) else -1.0

    book_alignment_score = 1.0 if (
        (side == "long" and order_book["book_imbalance"] > 0.0)
        or (side == "short" and order_book["book_imbalance"] < 0.0)
    ) else -1.0

    vwap_alignment_score = 1.0 if (
        (side == "long" and close >= f1["vwap_session"])
        or (side == "short" and close <= f1["vwap_session"])
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