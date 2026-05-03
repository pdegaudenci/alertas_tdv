"""
Servicio principal de validación.

Logica para:
- build_validation_step
- build_analysis_outputs
- run_validation

Orquesta:
alerta TradingView -> normalización -> market data -> scoring ->
probabilidad TP antes que SL -> pasos de validación -> respuesta final.

Mantiene la lógica original:
- validación solo completa para eventos ENTRY reales/lógicos
- skip controlado para eventos no-entry
- market_snapshot
- structure_snapshot
- alert_reused
- normalized_alert en la respuesta final
- validation_steps completo
- analysis_trace
- analysis_summary


"""

from typing import Any, Dict

from fastapi import HTTPException

from app.utils.time_utils import utc_now_iso
from app.utils.json_utils import sanitize_for_json
from app.utils.math_utils import safe_float

from app.services.alert_service import normalize_alert
from app.services.market_features_service import (
    collect_market_data,
    extract_latest_features,
    detect_swings,
)
from app.services.scoring_service import compute_external_scores
from app.services.probability_service import estimate_tp_before_sl_probability

from app.core.config import VALIDATION_THRESHOLD, MIN_SCORE_THRESHOLD
from app.core.logging import log_event
# ============================================================
# EVENT TYPES
# ============================================================

FULL_VALIDATION_EVENTS = {
    "LONG_INIT",
    "SHORT_INIT",
    "LONG_ENTRY",
    "SHORT_ENTRY",
    "REAL_LONG_ENTRY",
    "REAL_SHORT_ENTRY",
}

IMPULSE_EVENTS_ALLOWED_FOR_TRACKING = {
    "IMP_UP_AFTER_ADAPTIVE",
    "IMP_DN_AFTER_ADAPTIVE",
}

VALIDATION_ALLOWED_EVENTS = FULL_VALIDATION_EVENTS | IMPULSE_EVENTS_ALLOWED_FOR_TRACKING

# ============================================================
# VALIDATION HELPERS
# ============================================================

def build_validation_step(ok: bool, reason: str, details: dict | None = None) -> dict:
    return {
        "ok": ok,
        "status": "OK" if ok else "KO",
        "reason": reason,
        "details": details or {}
    }


def build_analysis_outputs(
    normalized_alert: dict,
    validation_steps: dict,
    probability_tp_before_sl: float | None,
    score_external: float | None,
    approve: bool
) -> tuple[list[str], dict]:
    trace = []

    event = normalized_alert.get("event", "UNKNOWN")
    side = str(normalized_alert.get("side", "")).upper()

    trace.append(f"Evento recibido: {event} ({side}).")

    step_context = validation_steps.get("context_validation", {})
    step_micro = validation_steps.get("microstructure_validation", {})
    step_flow = validation_steps.get("flow_validation", {})
    step_tp = validation_steps.get("tp_probability_validation", {})
    step_room = validation_steps.get("tp_room_validation", {})
    step_extension = validation_steps.get("extension_validation", {})

    if step_context.get("ok"):
        trace.append("El contexto técnico general está alineado con la dirección propuesta.")
    else:
        trace.append("El contexto técnico general no acompaña suficientemente la dirección propuesta.")

    if step_micro.get("ok"):
        trace.append("La microestructura de ejecución es favorable.")
    else:
        trace.append("La microestructura no ofrece suficiente apoyo operativo.")

    if step_flow.get("ok"):
        trace.append("El flujo reciente acompaña el movimiento esperado.")
    else:
        trace.append("El flujo reciente no confirma con claridad la continuación.")

    if step_room.get("ok"):
        trace.append("Existe espacio razonable para que el precio alcance el TP.")
    else:
        trace.append("El espacio hacia el TP parece limitado por estructura cercana.")

    if step_extension.get("ok"):
        trace.append("No se detecta un nivel de extensión suficiente para bloquear la entrada.")
    else:
        trace.append("La señal aparece demasiado extendida o tardía.")

    if probability_tp_before_sl is not None:
        trace.append(
            f"La probabilidad estimada de alcanzar TP antes que SL es {round(probability_tp_before_sl * 100, 2)}%."
        )

    if approve:
        final_conclusion = "La entrada queda aprobada por la Validation Layer."
    else:
        final_conclusion = "La entrada queda rechazada o no validada por la Validation Layer."

    trace.append(final_conclusion)

    summary = {
        "market_context": (
            "Contexto favorable."
            if step_context.get("ok")
            else "Contexto no suficientemente favorable."
        ),
        "execution_quality": (
            "Condiciones de ejecución aceptables."
            if step_micro.get("ok")
            else "Condiciones de ejecución débiles o mejorables."
        ),
        "risk_reading": (
            "Riesgo controlado."
            if step_tp.get("ok")
            else "Riesgo operativo elevado frente al objetivo."
        ),
        "final_conclusion": final_conclusion,
        "score_comment": (
            f"Score externo calculado: {round(score_external, 2)}."
            if score_external is not None
            else "Score externo no disponible."
        )
    }

    return trace, summary


# ============================================================
# MAIN VALIDATION
# ============================================================

async def run_validation(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_alert(payload)

    event = str(normalized.get("event") or "").upper().strip()

    if event not in FULL_VALIDATION_EVENTS:
        result = {
            "ok": True,
            "validated_at": utc_now_iso(),
            "message": "Validation skipped for non-entry event",
            "validation": {
                "approve": False,
                "confidence": 0,
                "probability_tp_before_sl": None,
                "score_external": None,
                "reason": [f"event_skipped:{event}"],
                "penalties": [],
                "event_type": event,
                "validation_steps": {
                    "event_gate": build_validation_step(
                        ok=False,
                        reason=f"event {event} is not eligible for full validation",
                        details={
                            "event": event,
                            "full_validation_events_allowed": sorted(list(FULL_VALIDATION_EVENTS)),
                            "tracking_only_events": sorted(list(IMPULSE_EVENTS_ALLOWED_FOR_TRACKING)),
                        }
                    )
                },
                "analysis_trace": [
                    f"Evento recibido: {event}.",
                    "No es un evento elegible para validación completa."
                ],
                "analysis_summary": {
                    "market_context": "No evaluado para este tipo de evento.",
                    "execution_quality": "No evaluada para este tipo de evento.",
                    "risk_reading": "No aplica.",
                    "final_conclusion": f"Validación omitida para evento {event}.",
                    "score_comment": "No se calculó score externo."
                }
            },
            "normalized_alert": {
                "schema_version": normalized.get("schema_version"),
                "message_type": normalized.get("message_type"),
                "symbol": normalized.get("symbol"),
                "side": normalized.get("side"),
                "event": normalized.get("event"),
                "tf": normalized.get("tf"),
                "entry_price": normalized.get("entry_price"),
                "tp_price_alert": normalized.get("tp_price"),
                "sl_price_alert": normalized.get("sl_price"),
                "quality_score_alert": normalized.get("quality_score_alert"),
                "quality_class_alert": normalized.get("quality_class_alert"),
            }
        }

        return sanitize_for_json(result)

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

    validation_steps = {}

    # ========================================================
    # EVENT GATE
    # ========================================================
    event_upper = str(normalized.get("event", "")).upper()
    entry_events = FULL_VALIDATION_EVENTS

    validation_steps["event_gate"] = build_validation_step(
        ok=event_upper in entry_events,
        reason=(
            "event eligible for full validation"
            if event_upper in entry_events
            else f"event {event_upper} is not eligible for full validation"
        ),
        details={
            "event": event_upper,
            "full_validation_events_allowed": sorted(list(entry_events))
        }
    )

    # ========================================================
    # CONTEXT VALIDATION
    # ========================================================
    context_ok = "htf_aligned" in ext["reasons"] or "ema_trend_aligned" in ext["reasons"]

    validation_steps["context_validation"] = build_validation_step(
        ok=context_ok,
        reason=(
            "HTF or trend context aligned"
            if context_ok
            else "HTF and trend context not sufficiently aligned"
        ),
        details={
            "regime": normalized.get("regime"),
            "phase": normalized.get("phase"),
            "dir_state": normalized.get("dir_state"),
            "htf_phase": normalized.get("htf_phase"),
            "htf_phase_strength": normalized.get("htf_phase_strength"),
            "adx_1m": f1["adx"],
            "close_1m": f1["close"],
            "vwap_1m": f1["vwap_session"]
        }
    )

    # ========================================================
    # MICROSTRUCTURE VALIDATION
    # ========================================================
    micro_ok = (
        safe_float(market["order_book"].get("spread_bps"), 999.0) <= 2.5 and
        (
            (normalized["side"] == "long" and safe_float(market["order_book"].get("book_imbalance"), 0.0) > 0.0) or
            (normalized["side"] == "short" and safe_float(market["order_book"].get("book_imbalance"), 0.0) < 0.0)
        )
    )

    validation_steps["microstructure_validation"] = build_validation_step(
        ok=micro_ok,
        reason=(
            "spread acceptable and order book aligned"
            if micro_ok
            else "spread or order book alignment not supportive"
        ),
        details={
            "spread_bps": market["order_book"].get("spread_bps"),
            "book_imbalance": market["order_book"].get("book_imbalance"),
            "bid_wall_detected": market["order_book"].get("bid_wall_detected"),
            "ask_wall_detected": market["order_book"].get("ask_wall_detected"),
            "vacuum_above": market["order_book"].get("vacuum_above"),
            "vacuum_below": market["order_book"].get("vacuum_below"),
        }
    )

    # ========================================================
    # FLOW VALIDATION
    # ========================================================
    flow_ok = (
        (normalized["side"] == "long" and safe_float(market["flow"].get("delta_qty"), 0.0) > 0.0) or
        (normalized["side"] == "short" and safe_float(market["flow"].get("delta_qty"), 0.0) < 0.0)
    )

    validation_steps["flow_validation"] = build_validation_step(
        ok=flow_ok,
        reason=(
            "trade flow aligned with expected side"
            if flow_ok
            else "trade flow not aligned with expected side"
        ),
        details={
            "delta_qty": market["flow"].get("delta_qty"),
            "buy_aggression": market["flow"].get("buy_aggression"),
            "sell_aggression": market["flow"].get("sell_aggression"),
            "trade_count": market["flow"].get("trade_count")
        }
    )

    # ========================================================
    # TP ROOM VALIDATION
    # ========================================================
    tp_room_ok = ext["backend_feature_pack"].get("tp_room_ok", 0.0) > 0

    validation_steps["tp_room_validation"] = build_validation_step(
        ok=tp_room_ok,
        reason=(
            "there is enough structural room to target TP"
            if tp_room_ok
            else "structure suggests limited room to TP"
        ),
        details={
            "last_swing_high": structure.get("last_swing_high"),
            "last_swing_low": structure.get("last_swing_low"),
            "distance_to_swing_high_pct": structure.get("distance_to_swing_high_pct"),
            "distance_to_swing_low_pct": structure.get("distance_to_swing_low_pct"),
            "distance_to_tp_pct_alert": normalized.get("distance_to_tp_pct_alert")
        }
    )

    # ========================================================
    # EXTENSION VALIDATION
    # ========================================================
    extension_ok = not normalized.get("too_extended_block_alert", False) and not normalized.get("late_trend_alert", False)

    validation_steps["extension_validation"] = build_validation_step(
        ok=extension_ok,
        reason=(
            "entry is not excessively extended or late"
            if extension_ok
            else "entry appears extended or late in trend"
        ),
        details={
            "too_extended_warn_alert": normalized.get("too_extended_warn_alert"),
            "too_extended_block_alert": normalized.get("too_extended_block_alert"),
            "late_trend_alert": normalized.get("late_trend_alert")
        }
    )

    # ========================================================
    # PROBABILITY VALIDATION
    # ========================================================
    tp_prob_ok = safe_float(prob.get("probability_tp_before_sl"), 0.0) >= VALIDATION_THRESHOLD

    validation_steps["tp_probability_validation"] = build_validation_step(
        ok=tp_prob_ok,
        reason=(
            "probability to hit TP before SL is above threshold"
            if tp_prob_ok
            else "probability to hit TP before SL is below threshold"
        ),
        details={
            "probability_tp_before_sl": prob.get("probability_tp_before_sl"),
            "threshold": VALIDATION_THRESHOLD,
            "barrier_component": prob.get("barrier_component"),
            "technical_component": prob.get("technical_component"),
            "ml_component": prob.get("ml_component")
        }
    )

    # ========================================================
    # SCORE VALIDATION
    # ========================================================
    score_ok = safe_float(ext.get("score_external"), 0.0) >= MIN_SCORE_THRESHOLD

    validation_steps["score_validation"] = build_validation_step(
        ok=score_ok,
        reason=(
            "external score above minimum threshold"
            if score_ok
            else "external score below minimum threshold"
        ),
        details={
            "score_external": ext.get("score_external"),
            "threshold": MIN_SCORE_THRESHOLD,
            "reasons": ext.get("reasons", []),
            "penalties": ext.get("penalties", [])
        }
    )

    approve = bool(
        safe_float(prob.get("probability_tp_before_sl"), 0.0) >= VALIDATION_THRESHOLD and
        safe_float(ext.get("score_external"), 0.0) >= MIN_SCORE_THRESHOLD and
        not normalized.get("too_extended_block_alert", False)
    )

    analysis_trace, analysis_summary = build_analysis_outputs(
        normalized_alert=normalized,
        validation_steps=validation_steps,
        probability_tp_before_sl=safe_float(prob.get("probability_tp_before_sl"), 0.0),
        score_external=safe_float(ext.get("score_external"), 0.0),
        approve=approve
    )

    log_event("validation_steps", validation_steps)
    log_event("analysis_trace", {
        "trace": analysis_trace,
        "summary": analysis_summary
    })

    confidence = round(safe_float(prob.get("probability_tp_before_sl"), 0.0) * 100.0, 2)
    entry_price = normalized["entry_price"] if safe_float(normalized["entry_price"], 0.0) > 0 else f1["close"]

    validation = {
        "approve": approve,
        "confidence": confidence,
        "side": normalized["side"],
        "symbol": normalized["symbol"],
        "event": normalized["event"],
        "entry_price": entry_price,
        "tp": prob.get("tp_price_used"),
        "sl": prob.get("sl_price_used"),
        "rr": safe_float(normalized.get("rr_ratio_alert")),
        "probability_tp_before_sl": round(safe_float(prob.get("probability_tp_before_sl"), 0.0), 4),
        "probability_model": prob.get("probability_model"),
        "barrier_component": round(safe_float(prob.get("barrier_component"), 0.0), 4),
        "technical_component": round(safe_float(prob.get("technical_component"), 0.0), 4),
        "ml_component": round(safe_float(prob.get("ml_component")), 4) if prob.get("ml_component") is not None else None,
        "score_external": round(safe_float(ext.get("score_external"), 0.0), 2),
        "quality_score_alert": round(safe_float(normalized.get("quality_score_alert"), 0.0), 2),
        "reason": ext.get("reasons", [])[:12],
        "penalties": ext.get("penalties", [])[:12],
        "validation_steps": validation_steps,
        "analysis_trace": analysis_trace,
        "analysis_summary": analysis_summary,
        "market_snapshot": {
            "close_1m": round(safe_float(f1["close"]), 4),
            "ema20_1m": round(safe_float(f1["ema20"]), 4),
            "ema50_1m": round(safe_float(f1["ema50"]), 4),
            "ema200_1m": round(safe_float(f1["ema200"]), 4),
            "adx_1m": round(safe_float(f1["adx"]), 2),
            "plus_di_1m": round(safe_float(f1["plus_di"]), 2),
            "minus_di_1m": round(safe_float(f1["minus_di"]), 2),
            "atr14_1m": round(safe_float(f1["atr14"]), 4),
            "rvol20_1m": round(safe_float(f1["rvol20"], 1.0), 3),
            "impulse_atr_1m": round(safe_float(f1["impulse_atr"]), 3),
            "dist_to_vwap_pct_1m": round(safe_float(f1["dist_to_vwap_pct"]), 4),
            "spread_bps": round(safe_float(market["order_book"].get("spread_bps")), 4),
            "book_imbalance": round(safe_float(market["order_book"].get("book_imbalance")), 4),
            "buy_aggression": round(safe_float(market["flow"].get("buy_aggression")), 4),
            "sell_aggression": round(safe_float(market["flow"].get("sell_aggression")), 4),
            "delta_qty": round(safe_float(market["flow"].get("delta_qty")), 6),
            "bid_wall_detected": market["order_book"].get("bid_wall_detected"),
            "ask_wall_detected": market["order_book"].get("ask_wall_detected"),
            "vacuum_above": market["order_book"].get("vacuum_above"),
            "vacuum_below": market["order_book"].get("vacuum_below"),
        },
        "structure_snapshot": {
            "last_swing_high": structure.get("last_swing_high"),
            "last_swing_low": structure.get("last_swing_low"),
            "distance_to_swing_high_pct": structure.get("distance_to_swing_high_pct"),
            "distance_to_swing_low_pct": structure.get("distance_to_swing_low_pct"),
            "range_mode": structure.get("range_mode"),
            "compression_box": structure.get("compression_box"),
        },
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

    result = {
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

    return sanitize_for_json(result)