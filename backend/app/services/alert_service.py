"""
Servicio de alertas TradingView.

Este archivo agrupa la lógica original relacionada con:
- parseo del body recibido desde TradingView
- normalización/canonical schema
- build_log
- normalize_alert
- build_history_item
- merge de logical_event_core + logical_event_extra por event_uid
"""

from typing import Any, Dict, Tuple
import json

from app.core.state import ASSEMBLED_EVENTS
from app.utils.time_utils import utc_now_iso
from app.utils.json_utils import sanitize_for_json
from app.utils.math_utils import safe_float, safe_int, strength_to_score


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


def first_non_empty(*values: Any) -> Any:
    """
    Devuelve el primer valor que no sea None ni string vacío.
    Importante: conserva 0 y False como valores válidos.
    """
    for value in values:
        if value is not None and value != "":
            return value
    return None


def ensure_canonical_schema(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    out = dict(payload)

    signal = out.get("signal", {}) if isinstance(out.get("signal"), dict) else {}
    execution = out.get("execution", {}) if isinstance(out.get("execution"), dict) else {}
    context = out.get("context", {}) if isinstance(out.get("context"), dict) else {}

    canonical_price = first_non_empty(
        signal.get("market_price"),
        signal.get("entry_price"),
        signal.get("price"),
        signal.get("close"),
        execution.get("entry_price"),
        execution.get("market_price"),
        out.get("price"),
        out.get("close"),
        out.get("entry_price"),
        out.get("market_price"),
    )

    canonical_entry_price = first_non_empty(
        signal.get("entry_price"),
        signal.get("market_price"),
        signal.get("price"),
        signal.get("close"),
        execution.get("entry_price"),
        execution.get("market_price"),
        out.get("entry_price"),
        out.get("market_price"),
        out.get("price"),
        out.get("close"),
    )

    out["signal"] = {
        **signal,
        "symbol": first_non_empty(signal.get("symbol"), out.get("symbol"), out.get("ticker"), "BTCUSDC"),
        "tf": first_non_empty(signal.get("tf"), out.get("tf"), out.get("timeframe"), "1m"),
        "event": first_non_empty(signal.get("event"), out.get("event")),
        "side": first_non_empty(signal.get("side"), out.get("side")),
        "price": canonical_price,
        "entry_price": canonical_entry_price,
        "setup": first_non_empty(signal.get("setup"), signal.get("setup_state"), out.get("setup")),
    }

    out["context"] = {
        **context,
        "regime": first_non_empty(context.get("regime"), out.get("regime")),
        "phase": first_non_empty(context.get("phase"), out.get("phase")),
        "dir_state": context.get("dir_state"),
        "mov_state": context.get("mov_state"),
        "liq_state": context.get("liq_state"),
    }

    existing_trade_plan = out.get("trade_plan", {}) if isinstance(out.get("trade_plan"), dict) else {}

    out["trade_plan"] = {
        **existing_trade_plan,
        "tp_price": first_non_empty(existing_trade_plan.get("tp_price"), execution.get("tp_price")),
        "sl_price": first_non_empty(existing_trade_plan.get("sl_price"), execution.get("sl_price")),
        "rr_ratio": first_non_empty(existing_trade_plan.get("rr_ratio"), execution.get("rr_ratio")),
        "distance_to_tp_pct": first_non_empty(
            existing_trade_plan.get("distance_to_tp_pct"),
            execution.get("distance_to_tp_pct"),
        ),
        "distance_to_sl_pct": first_non_empty(
            existing_trade_plan.get("distance_to_sl_pct"),
            execution.get("distance_to_sl_pct"),
        ),
    }

    return out

def assemble_event_payload(payload_raw: Dict[str, Any]) -> Dict[str, Any]:
    return ensure_canonical_schema(payload_raw)


def should_validate_payload(payload: Dict[str, Any]) -> bool:
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}

    event = str(
        signal.get("event")
        or payload.get("event")
        or ""
    ).upper().strip()

    message_type = str(
        payload.get("message_type")
        or ""
    ).lower().strip()

    valid_message_types = {
        "logical_event_full",
        "logical_event_core",
        "executed_event",
    }

    valid_events = {
        "LONG_INIT",
        "SHORT_INIT",
        "LONG_ENTRY",
        "SHORT_ENTRY",
        "REAL_LONG_ENTRY",
        "REAL_SHORT_ENTRY",
        "IMP_UP_AFTER_ADAPTIVE",
        "IMP_DN_AFTER_ADAPTIVE",
    }

    return message_type in valid_message_types and event in valid_events

def build_log(route: str, payload: dict, headers: dict | None = None) -> dict:
    canonical = ensure_canonical_schema(payload)

    signal = canonical.get("signal", {}) if isinstance(canonical.get("signal"), dict) else {}
    context = canonical.get("context", {}) if isinstance(canonical.get("context"), dict) else {}
    quality = canonical.get("quality", {}) if isinstance(canonical.get("quality"), dict) else {}

    return {
        "received_at": utc_now_iso(),
        "route": route,
        "schema_version": canonical.get("schema_version"),
        "message_type": canonical.get("message_type"),
        "event_uid": canonical.get("event_uid"),
        "symbol": signal.get("symbol") or canonical.get("symbol") or canonical.get("ticker"),
        "timeframe": signal.get("tf") or canonical.get("timeframe") or canonical.get("tf"),
        "event": signal.get("event") or canonical.get("event"),
        "side": signal.get("side") or canonical.get("side"),
        "setup": signal.get("setup") or canonical.get("setup"),
        "price": signal.get("price") or canonical.get("price"),
        "phase": context.get("phase") or canonical.get("phase"),
        "regime": context.get("regime"),
        "quality_score": quality.get("quality_score") or canonical.get("quality_score") or canonical.get("score"),
        "headers": headers or {},
    }


def normalize_alert(payload: Dict[str, Any]) -> Dict[str, Any]:
    canonical = ensure_canonical_schema(payload)

    signal = canonical.get("signal", {}) if isinstance(canonical.get("signal"), dict) else {}
    context = canonical.get("context", {}) if isinstance(canonical.get("context"), dict) else {}
    movement = canonical.get("movement", {}) if isinstance(canonical.get("movement"), dict) else {}
    liquidity = canonical.get("liquidity", {}) if isinstance(canonical.get("liquidity"), dict) else {}
    structure = canonical.get("structure", {}) if isinstance(canonical.get("structure"), dict) else {}
    trigger = canonical.get("trigger", {}) if isinstance(canonical.get("trigger"), dict) else {}
    quality = canonical.get("quality", {}) if isinstance(canonical.get("quality"), dict) else {}
    trade_plan = canonical.get("trade_plan", {}) if isinstance(canonical.get("trade_plan"), dict) else {}
    setup_timing = canonical.get("setup_timing", {}) if isinstance(canonical.get("setup_timing"), dict) else {}
    setup_validation = canonical.get("setup_validation", {}) if isinstance(canonical.get("setup_validation"), dict) else {}
    setup_context = canonical.get("setup_context", {}) if isinstance(canonical.get("setup_context"), dict) else {}
    sequence = canonical.get("sequence", {}) if isinstance(canonical.get("sequence"), dict) else {}
    htf_context = canonical.get("htf_context", {}) if isinstance(canonical.get("htf_context"), dict) else {}
    execution = canonical.get("execution", {}) if isinstance(canonical.get("execution"), dict) else {}
    ml_tracking = canonical.get("ml_tracking", {}) if isinstance(canonical.get("ml_tracking"), dict) else {}
    side = str(signal.get("side") or canonical.get("side") or "").lower().strip()
    symbol = str(signal.get("symbol") or canonical.get("symbol") or canonical.get("ticker") or "BTCUSDC").upper().strip()
    event = str(signal.get("event") or canonical.get("event") or "").upper().strip()
    tf = str(signal.get("tf") or canonical.get("tf") or canonical.get("timeframe") or "1m").strip()

    entry_price = safe_float(
        signal.get("entry_price")
        or signal.get("price")
        or signal.get("close")
        or canonical.get("price")
    )

    execution = canonical.get("execution", {}) if isinstance(canonical.get("execution"), dict) else {}

    tp_price = safe_float(trade_plan.get("tp_price") or execution.get("tp_price"))
    sl_price = safe_float(trade_plan.get("sl_price") or execution.get("sl_price"))

    if side not in {"long", "short"}:
        if "LONG" in event or "IMP_UP" in event:
            side = "long"
        elif "SHORT" in event or "IMP_DN" in event:
            side = "short"

    return {
        "schema_version": canonical.get("schema_version", "unknown"),
        "message_type": canonical.get("message_type", "unknown"),
        "event_uid": canonical.get("event_uid"),
        "source": canonical.get("source", {}),
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
        "execution": execution,
        "ml_tracking": ml_tracking,

        "symbol": symbol,
        "side": side,
        "event": event,
        "tf": tf,
        "entry_price": entry_price,
        "tp_price": tp_price,
        "sl_price": sl_price,

        "quality_score_alert": safe_float(quality.get("quality_score") or canonical.get("quality_score")),
        "quality_class_alert": quality.get("quality_class"),
        "quality_approved_alert": bool(quality.get("quality_approved", False)),
        "regime": context.get("regime"),
        "phase": context.get("phase"),
        "dir_state": context.get("dir_state"),
        "raw_dir_state": context.get("raw_dir_state"),
        "phase_strength": strength_to_score(context.get("phase_strength")),
        "regime_strength": strength_to_score(context.get("regime_strength")),
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
        "too_extended_warn_alert": bool(
            quality.get("too_extended_warn")
            or movement.get("too_extended_long_warn")
            or movement.get("too_extended_short_warn")
        ),
        "too_extended_block_alert": bool(
            quality.get("too_extended_block")
            or movement.get("too_extended_long_block")
            or movement.get("too_extended_short_block")
        ),
        "late_trend_alert": bool(
            quality.get("late_trend")
            or movement.get("late_long_trend")
            or movement.get("late_short_trend")
        ),
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
        "htf_phase_strength": strength_to_score(htf_context.get("htf_phase_strength")),
        "htf_phase_bias": htf_context.get("htf_phase_bias"),
        "htf_adx": safe_float(htf_context.get("htf_adx")),
        "rr_ratio_alert": safe_float(trade_plan.get("rr_ratio") or execution.get("rr_ratio")),
        "distance_to_tp_pct_alert": safe_float(trade_plan.get("distance_to_tp_pct") or execution.get("distance_to_tp_pct")),
        "distance_to_sl_pct_alert": safe_float(trade_plan.get("distance_to_sl_pct") or execution.get("distance_to_sl_pct")),
        "tp_perc_alert": safe_float(trade_plan.get("tp_perc")),
        "sl_perc_alert": safe_float(trade_plan.get("sl_perc")),
        "track_for_outcome": bool(
        ml_tracking.get("track_for_outcome")
        or signal.get("track_for_outcome", False)
        ),
        "candidate_type": (
            ml_tracking.get("candidate_type")
            or signal.get("candidate_type")
        ),
        "labeling_profile": ml_tracking.get("labeling_profile"),
        "labeling_window_bars": safe_int(ml_tracking.get("labeling_window_bars"), 20),
        "ambiguous_rule": ml_tracking.get("ambiguous_rule"),
        "timeout_rule": ml_tracking.get("timeout_rule"),
        "entry_reference": ml_tracking.get("entry_reference"),
        "tp_sl_source": ml_tracking.get("tp_sl_source"),
        "ml_target": ml_tracking.get("ml_target"),
        "exclude_ambiguous_from_binary": bool(
            ml_tracking.get("exclude_ambiguous_from_binary", True)
),
    }


def build_history_item(payload: dict, validation_result: dict | None = None) -> dict:
    canonical = ensure_canonical_schema(payload)

    signal = canonical.get("signal", {}) if isinstance(canonical.get("signal"), dict) else {}
    context = canonical.get("context", {}) if isinstance(canonical.get("context"), dict) else {}
    quality = canonical.get("quality", {}) if isinstance(canonical.get("quality"), dict) else {}
    htf_context = canonical.get("htf_context", {}) if isinstance(canonical.get("htf_context"), dict) else {}

    validation = validation_result.get("validation", {}) if isinstance(validation_result, dict) else {}

    return sanitize_for_json({
        "received_at": utc_now_iso(),
        "schema_version": canonical.get("schema_version"),
        "message_type": canonical.get("message_type"),
        "event_uid": canonical.get("event_uid"),
        "symbol": signal.get("symbol"),
        "tf": signal.get("tf"),
        "event": signal.get("event"),
        "side": signal.get("side"),
        "setup": signal.get("setup"),
        "price": signal.get("price"),
        "phase": context.get("phase"),
        "regime": context.get("regime"),
        "quality_score": quality.get("quality_score"),
        "htf_phase": htf_context.get("htf_phase"),
        "htf_phase_strength": htf_context.get("htf_phase_strength"),
        "approve": validation.get("approve"),
        "confidence": validation.get("confidence"),
        "probability_tp_before_sl": validation.get("probability_tp_before_sl"),
        "score_external": validation.get("score_external"),
        "reason": validation.get("reason", []),
        "penalties": validation.get("penalties", []),
    })


def merge_core_extra_payloads(core: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(core)

    for key in [
        "adaptive_algoalpha",
        "movement",
        "liquidity",
        "structure",
        "setup_timing",
        "setup_validation",
        "setup_context",
        "sequence",
        "htf_context",
    ]:
        if isinstance(extra.get(key), dict):
            merged[key] = extra[key]

    merged["message_type"] = "logical_event_full"
    merged["assembled_from"] = ["logical_event_core", "logical_event_extra"]
    merged["extra_received"] = True

    return ensure_canonical_schema(merged)


def assemble_core_extra_by_event_uid(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Devuelve:
    - payload ensamblado
    - True si ya está completo para persistir/procesar
    """
    message_type = str(payload.get("message_type") or "").lower()
    event_uid = str(payload.get("event_uid") or "").strip()

    if not event_uid:
        return ensure_canonical_schema(payload), True

    if event_uid not in ASSEMBLED_EVENTS:
        ASSEMBLED_EVENTS[event_uid] = {}

    buffer = ASSEMBLED_EVENTS[event_uid]

    if message_type == "logical_event_core":
        buffer["core"] = payload

    elif message_type == "logical_event_extra":
        buffer["extra"] = payload

    else:
        return ensure_canonical_schema(payload), True

    core = buffer.get("core")
    extra = buffer.get("extra")

    if core and extra:
        merged = merge_core_extra_payloads(core, extra)
        ASSEMBLED_EVENTS.pop(event_uid, None)
        return merged, True

    partial = ensure_canonical_schema(payload)
    partial["waiting_for_pair"] = True

    return partial, False