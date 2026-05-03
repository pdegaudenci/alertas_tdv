"""
Repositorio Supabase.

Logica para:
- inicializar cliente Supabase
- decidir si un payload debe persistirse
- extraer setup_id y event_id
- construir snapshots técnicos y microestructura
- insertar/upsert en alert_events
- upsert en trade_setups
- insertar validation_results
- leer histórico desde REST
- leer setups desde SDK

"""

from typing import Optional, Dict, Any
import os
import time
import traceback
import requests

from fastapi.responses import JSONResponse
from supabase import create_client, Client

from app.core.config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_ENABLED,
)
from app.core.logging import log_event, log_trace
from app.utils.time_utils import utc_now_iso
from app.utils.json_utils import sanitize_for_json
from app.utils.math_utils import safe_float, nested_get
from app.services.alert_service import normalize_alert, ensure_canonical_schema


supabase: Optional[Client] = None
SUPABASE_RUNTIME_ENABLED = SUPABASE_ENABLED

if SUPABASE_RUNTIME_ENABLED:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        log_event("supabase_init_ok", {
            "enabled": True,
            "url_present": bool(SUPABASE_URL),
        })
    except Exception as e:
        supabase = None
        SUPABASE_RUNTIME_ENABLED = False
        log_event("supabase_init_error", {
            "enabled": False,
            "error": str(e),
        })
else:
    log_event("supabase_init_skipped", {
        "enabled": False,
        "reason": "missing_env_vars",
    })

def should_persist_payload(payload: Dict[str, Any]) -> bool:
    """
    Decide si un payload debe persistirse en Supabase.

    Regla del proyecto:
    - Supabase = capa operativa / dashboard / estado reciente.
    - Databricks = histórico completo / analítica / ML / backtesting.

    Por tanto:
    - Supabase guarda eventos relevantes para operar.
    - Databricks guarda todos los payloads completos por separado.
    """
    payload = ensure_canonical_schema(payload)
    source = payload.get("source", {}) if isinstance(payload.get("source"), dict) else {}
    script = str(source.get("script") or payload.get("strategy_name") or "").strip()

    message_type = str(payload.get("message_type") or "").strip().lower()

    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    event = str(signal.get("event") or payload.get("event") or "").upper().strip()

    if not event:
        return False

    # ========================================================
    # 1. Siempre guardar eventos reales de ejecución
    # ========================================================

    if message_type == "executed_event":
        return event in {
            "REAL_LONG_ENTRY",
            "REAL_SHORT_ENTRY",
            "REAL_LONG_EXIT",
            "REAL_SHORT_EXIT",
            "EXECUTED_EXIT",
        }

    # ========================================================
    # 2. Guardar solo eventos lógicos completos
    #    No guardar core/extra sueltos en Supabase.
    #    El merge core+extra ya ocurre antes.
    # ========================================================

    if message_type not in {
        "logical_event_full",
        "logical_event",
    }:
        return False

    # ========================================================
    # 3. Eventos operativos relevantes para dashboard/app
    # ========================================================

    operational_events = {
        # INIT / señales tempranas
        "LONG_INIT",
        "SHORT_INIT",
        "LONG_INIT_AFTER_ADAPTIVE",
        "SHORT_INIT_AFTER_ADAPTIVE",

        # Impulsos relevantes
        "IMP_UP_AFTER_ADAPTIVE",
        "IMP_DN_AFTER_ADAPTIVE",

        # Entradas lógicas validadas por backend
        "LONG_ENTRY",
        "SHORT_ENTRY",

        # Entradas/salidas reales si llegasen como logical_event_full
        "REAL_LONG_ENTRY",
        "REAL_SHORT_ENTRY",
        "REAL_LONG_EXIT",
        "REAL_SHORT_EXIT",
        "EXECUTED_EXIT",

        # Cancelaciones
        "LONG_CANCEL",
        "SHORT_CANCEL",
        "CANCEL",
    }

    if event not in operational_events:
        return False

    # ========================================================
    # 4. Scripts conocidos del sistema
    # ========================================================

    known_scripts = {
        "PHASE_INDICATOR_V8_FULL_ALERTS",
        "SETUP_CLASSIFIER_MASTER_v7_3_FULL_API_ALERTS",
        "REGIME_PHASE_SETUP_QUALITY_MASTER_v1",
        "POSTMAN_TEST",
    }

    if script in known_scripts:
        return True

    # ========================================================
    # 5. Fallback controlado:
    #    Si el script viene vacío pero el payload tiene schema v2.0
    #    y es un evento operativo, lo dejamos persistir.
    # ========================================================

    schema_version = str(payload.get("schema_version") or "").strip()

    if schema_version == "2.0":
        return True

    return False

def extract_setup_id(payload: Dict[str, Any]) -> str:
    payload = ensure_canonical_schema(payload)
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}

    message_type = str(payload.get("message_type") or "").lower()
    parent_entry_uid = payload.get("parent_entry_uid")

    if message_type == "executed_event" and parent_entry_uid:
        return str(parent_entry_uid).strip()

    candidates = [
        payload.get("setup_id"),
        payload.get("event_uid"),
        signal.get("setup_id"),
        signal.get("event_uid"),
    ]

    for c in candidates:
        if c is not None and str(c).strip():
            return str(c).strip()

    symbol = str(signal.get("symbol") or payload.get("symbol") or payload.get("ticker") or "UNKNOWN").upper().strip()
    tf = str(signal.get("tf") or payload.get("tf") or payload.get("timeframe") or "UNKNOWN").strip()
    side = str(signal.get("side") or payload.get("side") or "unknown").lower().strip()
    event = str(signal.get("event") or payload.get("event") or "unknown").upper().strip()

    return f"{symbol}_{tf}_{side}_{event}_{int(time.time() * 1000)}"


def extract_event_id(payload: Dict[str, Any]) -> str:
    payload = ensure_canonical_schema(payload)
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}

    candidates = [
        payload.get("event_id"),
        payload.get("event_uid"),
        signal.get("event_uid"),
    ]

    for c in candidates:
        if c is not None and str(c).strip():
            return str(c).strip()

    setup_id = extract_setup_id(payload)
    return f"{setup_id}_{int(time.time() * 1000)}"


def build_normalized_payload_for_db(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        canonical_payload = ensure_canonical_schema(payload)
        normalized = normalize_alert(canonical_payload)
        return sanitize_for_json(normalized)
    except Exception:
        return sanitize_for_json(ensure_canonical_schema(payload))


def build_lifecycle_state(payload: Dict[str, Any], validation_result: Optional[Dict[str, Any]] = None) -> str:
    payload = ensure_canonical_schema(payload)
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    event = str(signal.get("event") or payload.get("event") or "").upper().strip()

    if event in {"WATCH", "LONG_WATCH", "SHORT_WATCH"}:
        return "WATCH"

    if event in {"ARMED", "LONG_ARMED", "SHORT_ARMED"}:
        return "ARMED"

    if event in {
        "LONG_INIT",
        "SHORT_INIT",
        "LONG_INIT_AFTER_ADAPTIVE",
        "SHORT_INIT_AFTER_ADAPTIVE",
        "IMP_UP_AFTER_ADAPTIVE",
        "IMP_DN_AFTER_ADAPTIVE",}:
        quality = payload.get("quality", {}) if isinstance(payload.get("quality"), dict) else {}
        return "VALIDATED" if quality.get("quality_approved") is True else "INIT_RECEIVED"

    if event in {"LONG_ENTRY", "SHORT_ENTRY"}:
        if isinstance(validation_result, dict):
            validation = validation_result.get("validation", {}) if isinstance(validation_result.get("validation"), dict) else {}
            if validation.get("approve") is True:
                return "VALIDATED"
            return "REJECTED"
        return "ENTRY_PENDING"

    if event in {"REAL_LONG_ENTRY", "REAL_SHORT_ENTRY"}:
        return "OPEN"

    if event in {"REAL_LONG_EXIT", "REAL_SHORT_EXIT", "EXECUTED_EXIT"}:
        return "CLOSED"

    if event in {"CANCEL", "LONG_CANCEL", "SHORT_CANCEL"}:
        return "CANCELLED"

    return event or "UNKNOWN"


def build_technical_state_for_db(payload: Dict[str, Any], validation_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = ensure_canonical_schema(payload)
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    movement = payload.get("movement", {}) if isinstance(payload.get("movement"), dict) else {}
    liquidity = payload.get("liquidity", {}) if isinstance(payload.get("liquidity"), dict) else {}
    trigger = payload.get("trigger", {}) if isinstance(payload.get("trigger"), dict) else {}
    htf_context = payload.get("htf_context", {}) if isinstance(payload.get("htf_context"), dict) else {}

    market_snapshot = {}
    structure_snapshot = {}

    if isinstance(validation_result, dict):
        val = validation_result.get("validation", {}) if isinstance(validation_result.get("validation"), dict) else {}
        market_snapshot = val.get("market_snapshot", {}) if isinstance(val.get("market_snapshot"), dict) else {}
        structure_snapshot = val.get("structure_snapshot", {}) if isinstance(val.get("structure_snapshot"), dict) else {}

    return sanitize_for_json({
        "symbol": signal.get("symbol") or payload.get("symbol") or payload.get("ticker"),
        "timeframe": signal.get("tf") or payload.get("tf") or payload.get("timeframe"),
        "event": signal.get("event") or payload.get("event"),
        "side": signal.get("side") or payload.get("side"),
        "phase": context.get("phase"),
        "regime": context.get("regime"),
        "dir_state": context.get("dir_state"),
        "raw_dir_state": context.get("raw_dir_state"),
        "phase_strength": context.get("phase_strength"),
        "regime_strength": context.get("regime_strength"),
        "mov_state": movement.get("mov_state"),
        "liq_state": liquidity.get("liq_state"),
        "sweep_high": liquidity.get("sweep_high"),
        "sweep_low": liquidity.get("sweep_low"),
        "absorb_bull": liquidity.get("absorb_bull"),
        "absorb_bear": liquidity.get("absorb_bear"),
        "trigger_alignment": trigger.get("trigger_alignment"),
        "trigger_long": trigger.get("trigger_long"),
        "trigger_short": trigger.get("trigger_short"),
        "ast_dir": trigger.get("ast_dir"),
        "hull_bull": trigger.get("hull_bull"),
        "hull_bear": trigger.get("hull_bear"),
        "ast_bull": trigger.get("ast_bull"),
        "ast_bear": trigger.get("ast_bear"),
        "trigger_age_bars": trigger.get("trigger_age_bars"),
        "htf_tf": htf_context.get("htf_tf"),
        "htf_phase": htf_context.get("htf_phase"),
        "htf_phase_strength": htf_context.get("htf_phase_strength"),
        "htf_phase_bias": htf_context.get("htf_phase_bias"),
        "htf_adx": htf_context.get("htf_adx"),
        "market_snapshot": market_snapshot,
        "structure_snapshot": structure_snapshot,
    })


def build_microstructure_state_for_db(validation_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not isinstance(validation_result, dict):
        return {}

    validation = validation_result.get("validation", {}) if isinstance(validation_result.get("validation"), dict) else {}
    market_snapshot = validation.get("market_snapshot", {}) if isinstance(validation.get("market_snapshot"), dict) else {}

    return sanitize_for_json({
        "spread_bps": market_snapshot.get("spread_bps"),
        "book_imbalance": market_snapshot.get("book_imbalance"),
        "buy_aggression": market_snapshot.get("buy_aggression"),
        "sell_aggression": market_snapshot.get("sell_aggression"),
        "delta_qty": market_snapshot.get("delta_qty"),
        "bid_wall_detected": market_snapshot.get("bid_wall_detected"),
        "ask_wall_detected": market_snapshot.get("ask_wall_detected"),
        "vacuum_above": market_snapshot.get("vacuum_above"),
        "vacuum_below": market_snapshot.get("vacuum_below"),
        "adx_1m": market_snapshot.get("adx_1m"),
        "plus_di_1m": market_snapshot.get("plus_di_1m"),
        "minus_di_1m": market_snapshot.get("minus_di_1m"),
        "atr14_1m": market_snapshot.get("atr14_1m"),
        "rvol20_1m": market_snapshot.get("rvol20_1m"),
        "impulse_atr_1m": market_snapshot.get("impulse_atr_1m"),
        "dist_to_vwap_pct_1m": market_snapshot.get("dist_to_vwap_pct_1m"),
    })


async def supabase_insert_alert_event(
    payload: Dict[str, Any],
    validation_result: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return None
    payload = ensure_canonical_schema(payload)
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    source_obj = payload.get("source", {}) if isinstance(payload.get("source"), dict) else {}
    quality = payload.get("quality", {}) if isinstance(payload.get("quality"), dict) else {}
    execution = payload.get("execution", {}) if isinstance(payload.get("execution"), dict) else {}

    event_id = extract_event_id(payload)
    setup_id = extract_setup_id(payload)

    symbol = str(
        signal.get("symbol") or
        payload.get("symbol") or
        payload.get("ticker") or
        "UNKNOWN"
    ).upper().strip()

    timeframe = str(
        signal.get("tf") or
        payload.get("tf") or
        payload.get("timeframe") or
        "UNKNOWN"
    ).strip()

    alert_type = str(
        signal.get("event") or
        payload.get("event") or
        "UNKNOWN"
    ).upper().strip()

    side = str(
        signal.get("side") or
        payload.get("side") or
        ""
    ).lower().strip() or None

    strategy_name = (
        source_obj.get("script") or
        payload.get("strategy_name")
    )

    row = {
        "event_id": event_id,
        "setup_id": setup_id,

        "symbol": symbol,
        "timeframe": timeframe,
        "strategy_name": strategy_name,
        "alert_type": alert_type,
        "side": side,

        "source": source_obj.get("platform") or "tradingview",
        "status": build_lifecycle_state(payload, validation_result),

        "schema_version": payload.get("schema_version"),
        "message_type": payload.get("message_type"),
        "event_uid": payload.get("event_uid"),
        "parent_entry_uid": payload.get("parent_entry_uid"),
        "parent_event_uid": payload.get("parent_entry_uid"),
        "script_name": source_obj.get("script"),
        "quality_approved": bool(quality.get("quality_approved", False)),

        "exit_reason": execution.get("exit_reason"),
        "tp_hit": execution.get("tp_hit"),
        "sl_hit": execution.get("sl_hit"),

        "raw_payload": sanitize_for_json(payload),
        "normalized_payload": build_normalized_payload_for_db(payload),
        "technical_state": build_technical_state_for_db(payload, validation_result),
        "microstructure_state": build_microstructure_state_for_db(validation_result),
    }

    try:
        resp = (
            supabase
            .table("alert_events")
            .upsert(row, on_conflict="event_id")
            .execute()
        )

        data = resp.data or []

        if data and isinstance(data, list):
            inserted_id = data[0].get("id")

            log_event("supabase_alert_event_upsert_ok", {
                "event_id": event_id,
                "setup_id": setup_id,
                "event_uid": payload.get("event_uid"),
                "parent_entry_uid": payload.get("parent_entry_uid"),
                "db_id": inserted_id,
                "alert_type": alert_type,
                "message_type": payload.get("message_type"),
            })

            return inserted_id

        log_event("supabase_alert_event_upsert_ok", {
            "event_id": event_id,
            "setup_id": setup_id,
            "event_uid": payload.get("event_uid"),
            "db_id": None,
        })

        return None

    except Exception as e:
        log_event("supabase_alert_event_upsert_error", {
            "event_id": event_id,
            "setup_id": setup_id,
            "event_uid": payload.get("event_uid"),
            "error": str(e),
        })
        return None


async def supabase_upsert_trade_setup(
    payload: Dict[str, Any],
    validation_result: Optional[Dict[str, Any]] = None,
    alert_event_db_id: Optional[str] = None,
) -> None:
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return
    payload = ensure_canonical_schema(payload)
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    setup_id = extract_setup_id(payload)

    validation = validation_result.get("validation", {}) if isinstance(validation_result, dict) else {}

    row = {
        "setup_id": setup_id,
        "symbol": str(signal.get("symbol") or payload.get("symbol") or payload.get("ticker") or "UNKNOWN").upper().strip(),
        "timeframe": str(signal.get("tf") or payload.get("tf") or payload.get("timeframe") or "UNKNOWN").strip(),
        "side": str(signal.get("side") or payload.get("side") or "").lower().strip() or None,
        "lifecycle_state": build_lifecycle_state(payload, validation_result),
        "last_alert_event_id": alert_event_db_id,
        "confidence": safe_float(validation.get("confidence")),
        "validation_status": (
            "accepted" if validation.get("approve") is True else
            "rejected" if validation.get("approve") is False else
            "pending"
        ),
        "entry_price": safe_float(validation.get("entry_price")),
        "stop_loss": safe_float(validation.get("sl")),
        "take_profit": safe_float(validation.get("tp")),
        "latest_context": build_technical_state_for_db(payload, validation_result),
        "latest_validation": sanitize_for_json(validation) if validation else None,
        "metadata": sanitize_for_json({
            "event_uid": payload.get("event_uid"),
            "message_type": payload.get("message_type"),
            "schema_version": payload.get("schema_version"),
        }),
        "updated_at": utc_now_iso(),
    }

    try:
        supabase.table("trade_setups").upsert(row, on_conflict="setup_id").execute()
        log_event("supabase_trade_setup_upsert_ok", {
            "setup_id": setup_id,
            "lifecycle_state": row["lifecycle_state"],
        })
    except Exception as e:
        log_event("supabase_trade_setup_upsert_error", {
            "setup_id": setup_id,
            "error": str(e),
        })


async def supabase_insert_validation_result(
    payload: Dict[str, Any],
    validation_result: Optional[Dict[str, Any]] = None,
    alert_event_db_id: Optional[str] = None,
) -> None:
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return
async def supabase_insert_validation_result(
    payload: Dict[str, Any],
    validation_result: Optional[Dict[str, Any]] = None,
    alert_event_db_id: Optional[str] = None,
) -> None:
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return

    payload = ensure_canonical_schema(payload)

    if not isinstance(validation_result, dict):
        return
    if not isinstance(validation_result, dict):
        return

    validation = validation_result.get("validation", {}) if isinstance(validation_result.get("validation"), dict) else {}

    if not validation:
        return

    row = {
        "setup_id": extract_setup_id(payload),
        "alert_event_id": alert_event_db_id,
        "accepted": bool(validation.get("approve", False)),
        "confidence": safe_float(validation.get("confidence")),
        "probability_tp": safe_float(validation.get("probability_tp_before_sl")),
        "probability_sl": round(1.0 - safe_float(validation.get("probability_tp_before_sl"), 0.0), 4) if validation.get("probability_tp_before_sl") is not None else None,
        "rr_estimate": safe_float(validation.get("rr")),
        "validation_reason": "; ".join(validation.get("reason", [])[:12]) if isinstance(validation.get("reason"), list) else None,
        "model_version": os.getenv("VALIDATION_MODEL_VERSION", "rules_v1"),
        "validator_name": "validation_layer",
        "features": sanitize_for_json({
            "alert_reused": validation.get("alert_reused"),
            "market_snapshot": validation.get("market_snapshot"),
            "structure_snapshot": validation.get("structure_snapshot"),
            "validation_steps": validation.get("validation_steps"),
        }),
        "decision_payload": sanitize_for_json(validation_result),
    }

    try:
        supabase.table("validation_results").insert(row).execute()
        log_event("supabase_validation_result_insert_ok", {
            "setup_id": row["setup_id"],
            "accepted": row["accepted"],
        })
    except Exception as e:
        log_event("supabase_validation_result_insert_error", {
            "setup_id": row["setup_id"],
            "error": str(e),
        })



async def persist_to_supabase(
    payload: Dict[str, Any],
    validation_result: Optional[Dict[str, Any]] = None,
    trace_id: str = "-",
) -> None:
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        log_trace(trace_id, "supabase_persist_skipped", {
            "enabled": SUPABASE_RUNTIME_ENABLED,
            "client_available": supabase is not None,
        })
        return

    payload = ensure_canonical_schema(payload)

    try:
        if not should_persist_payload(payload):
            log_trace(trace_id, "supabase_persist_skipped_by_filter", {
                "script": nested_get(payload, "source", "script"),
                "message_type": payload.get("message_type"),
                "event_uid": payload.get("event_uid"),
                "event": nested_get(payload, "signal", "event"),
                "quality_approved": nested_get(payload, "quality", "quality_approved"),
                "parent_entry_uid": payload.get("parent_entry_uid"),
            })
            return

        setup_id = extract_setup_id(payload)
        event_id = extract_event_id(payload)

        log_trace(trace_id, "supabase_persist_start", {
            "script": nested_get(payload, "source", "script"),
            "message_type": payload.get("message_type"),
            "event": nested_get(payload, "signal", "event"),
            "side": nested_get(payload, "signal", "side"),
            "symbol": nested_get(payload, "signal", "symbol"),
            "setup_id": setup_id,
            "event_id": event_id,
            "event_uid": payload.get("event_uid"),
            "parent_entry_uid": payload.get("parent_entry_uid"),
        })

        alert_event_db_id = await supabase_insert_alert_event(payload, validation_result)

        log_trace(trace_id, "supabase_alert_event_done", {
            "setup_id": setup_id,
            "event_id": event_id,
            "alert_event_db_id": alert_event_db_id,
        })

        await supabase_upsert_trade_setup(payload, validation_result, alert_event_db_id)

        log_trace(trace_id, "supabase_trade_setup_done", {
            "setup_id": setup_id,
        })

        await supabase_insert_validation_result(payload, validation_result, alert_event_db_id)

        log_trace(trace_id, "supabase_validation_result_done", {
            "setup_id": setup_id,
        })

        log_trace(trace_id, "supabase_persist_done", {
            "ok": True,
            "setup_id": setup_id,
            "event_id": event_id,
            "alert_event_db_id": alert_event_db_id,
        })

    except Exception as e:
        log_trace(trace_id, "supabase_persist_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }, level="ERROR")


async def get_alerts_supabase_service(limit: int = 50):
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "Supabase not configured",
                "items": [],
            },
        )

    try:
        limit = max(1, min(int(limit), 100))

        log_event("supabase_url_debug", {
            "supabase_url": SUPABASE_URL,
            "host": SUPABASE_URL.replace("https://", "").replace("http://", ""),
        })

        url = f"{SUPABASE_URL}/rest/v1/alert_events"

        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        params = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
        }

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()

        rows = response.json() or []

        items = []

        for row in rows:
            normalized = row.get("normalized_payload") or {}
            technical = row.get("technical_state") or {}
            micro = row.get("microstructure_state") or {}
            raw = row.get("raw_payload") or {}

            context = raw.get("context", {}) if isinstance(raw.get("context"), dict) else {}
            movement = raw.get("movement", {}) if isinstance(raw.get("movement"), dict) else {}
            liquidity = raw.get("liquidity", {}) if isinstance(raw.get("liquidity"), dict) else {}
            trigger = raw.get("trigger", {}) if isinstance(raw.get("trigger"), dict) else {}
            htf_context = raw.get("htf_context", {}) if isinstance(raw.get("htf_context"), dict) else {}

            items.append({
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "event_id": row.get("event_id"),
                "setup_id": row.get("setup_id"),
                "symbol": row.get("symbol"),
                "tf": row.get("timeframe"),
                "event": row.get("alert_type"),
                "side": row.get("side"),
                "status": row.get("status"),
                "strategy_name": row.get("strategy_name"),
                "phase": technical.get("phase") or context.get("phase"),
                "regime": technical.get("regime") or context.get("regime"),
                "dir_state": technical.get("dir_state") or context.get("dir_state"),
                "mov_state": technical.get("mov_state") or movement.get("mov_state"),
                "liq_state": technical.get("liq_state") or liquidity.get("liq_state"),
                "htf_phase": technical.get("htf_phase") or htf_context.get("htf_phase"),
                "trigger_alignment": technical.get("trigger_alignment") or trigger.get("trigger_alignment"),
                "spread_bps": micro.get("spread_bps"),
                "book_imbalance": micro.get("book_imbalance"),
                "raw_payload": row.get("raw_payload"),
                "normalized_payload": normalized,
                "technical_state": technical,
                "microstructure_state": micro,
            })

        return {
            "ok": True,
            "count": len(items),
            "items": sanitize_for_json(items),
        }

    except Exception as e:
        log_event("supabase_history_read_error", {
            "error": str(e),
            "traceback": traceback.format_exc(),
        })

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "Could not read alerts from Supabase REST",
                "error": str(e),
                "items": [],
            },
        )


async def get_setups_supabase_service(limit: int = 50):
    if not SUPABASE_RUNTIME_ENABLED or supabase is None:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "Supabase not configured",
            },
        )

    try:
        resp = (
            supabase
            .table("trade_setups")
            .select("*")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )

        rows = resp.data or []

        return {
            "ok": True,
            "count": len(rows),
            "items": sanitize_for_json(rows),
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "Could not read trade_setups from Supabase",
                "error": str(e),
            },
        )