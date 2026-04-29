"""
Servicio de probabilidad TP antes que SL.

Este archivo conserva la lógica original del index.py para:
- estimar probabilidad de alcanzar TP antes que SL
- fórmula de barrera tipo Brownian first-passage
- componente técnico mediante score/logit
- hook opcional a modelo sklearn/joblib

"""

from typing import Any, Dict, Optional

import math
import numpy as np
from scipy.special import expit

from app.core.config import SKLEARN_MODEL, SKLEARN_FEATURE_ORDER
from app.utils.math_utils import safe_float, clip, sign_for_side


def first_hit_probability_barrier(
    side: str,
    entry_price: float,
    tp_price: float,
    sl_price: float,
    mu_per_bar: float,
    sigma_per_bar: float,
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
    score_external: float,
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
    adx_bonus = max(backend_features.get("adx", 0.0) - 18.0, 0.0) * 0.0002 * (
        1 if backend_features.get("trend_aligned", 0.0) > 0 else -0.3
    )

    mu_per_bar = ret_mean + ema_alignment + flow_alignment + book_alignment + vwap_alignment + adx_bonus
    sigma_per_bar = max(backend_features.get("ret_std_20", 0.0), 1e-6)

    barrier_prob = first_hit_probability_barrier(
        side=side,
        entry_price=entry_price,
        tp_price=tp_price,
        sl_price=sl_price,
        mu_per_bar=mu_per_bar,
        sigma_per_bar=sigma_per_bar,
    )

    # Technical probability from score + alert state
    quality_alert = safe_float(normalized_alert.get("quality_score_alert"), 50.0)
    trigger_alignment = safe_float(normalized_alert.get("trigger_alignment"), 0.0)
    htf_strength = safe_float(normalized_alert.get("htf_phase_strength"), 0.0)
    ext_penalty = 8.0 if normalized_alert.get("too_extended_block_alert") else (4.0 if normalized_alert.get("too_extended_warn_alert") else 0.0)
    late_penalty = 4.0 if normalized_alert.get("late_trend_alert") else 0.0

    technical_raw = (
        (0.55 * score_external)
        + (0.25 * quality_alert)
        + (0.10 * trigger_alignment)
        + (0.10 * htf_strength)
        - ext_penalty
        - late_penalty
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