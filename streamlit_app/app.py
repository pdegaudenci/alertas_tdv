import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pytz
import requests
import streamlit as st
from scipy.signal import argrelextrema
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from streamlit_autorefresh import st_autorefresh
import numpy as np
import pandas as pd
import pytz
import requests
import streamlit as st
from scipy.signal import argrelextrema
from core.config import (
    BACKEND_BASE_URL,
    BACKEND_LATEST_URL,
    BACKEND_ALERTS_URL,
    BACKEND_VALIDATION_URL,
    BACKEND_ALERTS_SUPABASE_URL,
    BINANCE_BASE_URLS,
    LOG_FILE,
    PAGE_TITLE,
    PAGE_ICON,
    PAGE_LAYOUT,
    DEFAULT_SYMBOL,
    CACHE_TTL_SECONDS,
)

from core.constants import (
    TP_BASE,
    SL_BASE,
    RISK_REWARD_WEIGHT,
    CAPITAL_EUR,
    RIESGO_POR_TRADE,
    APALANCAMIENTO,
    TP_REAL,
    SL_REAL,
    COMISION,
)

from core.session_state import init_session_state
from utils.math_utils import safe_float, rating_score, calcular_trailing
from utils.time_utils import madrid_to_utc_timestamp

from clients.backend_client import (
    fetch_backend_json,
    get_latest_backend_data,
    get_latest_validation_data,
    get_alerts_history,
    get_alerts_history_supabase,
    get_setups_supabase,
    health_backend,
    health_binance,
    health_supabase,
)
from services.market_data_service import obtener_datos_binance
from services.indicators_service import (
    ema,
    rsi,
    atr,
    roc,
    bbands,
    vwap,
    adx_dmi,
    supertrend,
    preparar_tf,
    preparar_1m,
    preparar_5m_contexto,
)
from services.liquidity_service import (
    detectar_pivots,
    contar_toques,
    agrupar_zonas,
    market_liquidity_risk,
    liquidity_risk_explained,
    construir_liquidity_engine,
)

from services.context_service import construir_contexto
from services.mtf_service import (
    emas_abiertas_5m,
    evaluar_mtf,
)

from services.trade_engine_service import (
    compute_trade_levels,
    calcular_posicion_real,
)

from services.probability_service import (
    probabilidad_tp_real,
    probabilidad_rentable,
)

from services.backtest_service import (
    log_signal,
    condiciones_similares,
    probabilidad_historica,
    backtest,
)

from services.explanation_service import (
    explicacion_prob_mercado,
    explicacion_mercado_fuerza,
    explicacion_fase,
    explicacion_climax,
    explicacion_adx_cayendo,
    explicacion_prob_entry,
    explicacion_momentum_bajista,
    explicacion_momentum_alcista,
    explicacion_rsi_saludable,
    explicacion_microtendencia_contraria,
    explicacion_vwap,
    explicacion_sin_energia,
    explicacion_compresion_extrema,
    explicacion_prob_tp_real,
    explicacion_prob_rentable,
    explicacion_calidad_setup,
)

from components.ui_helpers import (
    render_info_item,
    render_json_expander,
    render_text_list,
    render_section_divider,
)

from services.alert_view_service import (
    unwrap_latest_response,
    extract_latest_alert_summary,
    build_alert_history_dataframe,
    build_alert_expander_title,
    extract_alert_detail,
)

from services.validation_view_service import (
    extract_validation_block,
    build_validation_metrics,
    extract_validation_sections,
    get_approve_status_message,
)

from views.sidebar import (
    render_initial_backend_sidebar,
    render_market_sidebar,
)

from views.backend_monitor_view import render_backend_monitor_tab
from views.context_view import render_context_tab
from views.liquidity_view import render_liquidity_tab
from views.mtf_view import render_mtf_tab
from views.backtest_view import render_backtest_tab
from views.trade_evaluator_view import render_trade_evaluator_tab
# ============================================================
# STREAMLIT PAGE
# ============================================================
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=PAGE_LAYOUT,
)

init_session_state()


st.title("Panel de alertas TradingView")

sidebar_backend_state = render_initial_backend_sidebar()
auto_refresh = sidebar_backend_state["auto_refresh"]
refresh_seconds = sidebar_backend_state["refresh_seconds"]

if st.button("Cargar última alerta"):
    try:
        data = get_latest_backend_data()

        if not data.get("ok"):
            st.error(data.get("message", "Backend no disponible"))
            st.json(data)
        else:
            st.success("Backend conectado correctamente")

            st.subheader("Última señal")
            st.write("Ticker:", data.get("symbol", "-"))
            st.write("Side:", data.get("side", "-"))
            st.write("Setup:", data.get("setup", "-"))
            st.write("Evento:", data.get("event", "-"))
            st.write("Score:", data.get("quality_score", "-"))
            st.write("Timeframe:", data.get("timeframe", "-"))
            st.write("Precio:", data.get("price", "-"))
            st.write("Phase:", data.get("phase", "-"))
            st.write("Regime:", data.get("regime", "-"))
            st.write("Phase 5m:", data.get("phase_5m", "-"))
            st.write("Strength 5m:", data.get("strength_5m", "-"))
            st.write("Recibida:", data.get("received_at", "-"))

            # aquí sigue tu bloque original sin cambios

            validation = data.get("validation", {}) or {}
            validation_block = validation.get("validation", {}) if isinstance(validation, dict) else {}

            st.markdown("---")
            st.subheader("Resultado global de validación")

            approve = validation_block.get("approve")
            confidence = validation_block.get("confidence")
            prob_tp = validation_block.get("probability_tp_before_sl")
            score_external = validation_block.get("score_external")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Approve", "YES" if approve is True else "NO" if approve is False else "-")
            c2.metric("Confidence", f"{confidence}%" if confidence is not None else "-")
            c3.metric(
                "Prob TP antes SL",
                f"{round(prob_tp * 100, 2)}%" if isinstance(prob_tp, (float, int)) and prob_tp <= 1 else prob_tp if prob_tp is not None else "-"
            )
            c4.metric("Score externo", score_external if score_external is not None else "-")

            st.write("TP:", validation_block.get("tp", "-"))
            st.write("SL:", validation_block.get("sl", "-"))
            st.write("RR:", validation_block.get("rr", "-"))

            validation_steps = validation_block.get("validation_steps", {}) or {}
            analysis_trace = validation_block.get("analysis_trace", []) or []
            analysis_summary = validation_block.get("analysis_summary", {}) or {}
            alert_reused = validation_block.get("alert_reused", {}) or {}
            market_snapshot = validation_block.get("market_snapshot", {}) or {}
            structure_snapshot = validation_block.get("structure_snapshot", {}) or {}

            # ============================================================
            # BLOQUE A - ESTADO TÉCNICO ANALIZADO DESDE ALERTA PINE SCRIPT
            # ============================================================
            st.markdown("---")
            st.subheader("A) Estado técnico analizado desde alerta Pine Script")

            col_a1, col_a2, col_a3 = st.columns(3)

            with col_a1:
                st.markdown("### Contexto Pine")
                st.write("Regime:", alert_reused.get("regime", "-"))
                st.write("Phase:", alert_reused.get("phase", "-"))
                st.write("Dir state:", alert_reused.get("dir_state", "-"))
                st.write("Mov state:", alert_reused.get("mov_state", "-"))
                st.write("Liq state:", alert_reused.get("liq_state", "-"))

            with col_a2:
                st.markdown("### HTF Pine")
                st.write("HTF phase:", alert_reused.get("htf_phase", "-"))
                st.write("HTF phase strength:", alert_reused.get("htf_phase_strength", "-"))
                st.write("Trigger alignment:", alert_reused.get("trigger_alignment", "-"))

            with col_a3:
                st.markdown("### Riesgos Pine")
                st.write("Too extended warn:", alert_reused.get("too_extended_warn_alert", "-"))
                st.write("Too extended block:", alert_reused.get("too_extended_block_alert", "-"))
                st.write("Late trend:", alert_reused.get("late_trend_alert", "-"))

            st.markdown("### Steps relacionados con contexto técnico Pine")

            pine_steps = [
                "event_gate",
                "context_validation",
                "extension_validation",
                "score_validation"
            ]

            for step_name in pine_steps:
                step_data = validation_steps.get(step_name, {})
                if step_data:
                    titulo = f"{step_name} → {step_data.get('status', '-')}"
                    if step_data.get("ok"):
                        st.success(titulo)
                    else:
                        st.error(titulo)
                    st.write("Motivo:", step_data.get("reason", "-"))
                    if step_data.get("details"):
                        with st.expander(f"Detalles de {step_name}", expanded=False):
                            st.json(step_data.get("details", {}))

            if analysis_summary:
                st.markdown("### Conclusión del estado técnico")
                st.info(f"Contexto: {analysis_summary.get('market_context', '-')}")
                st.info(f"Riesgo: {analysis_summary.get('risk_reading', '-')}")

            # ============================================================
            # BLOQUE B - MICROESTRUCTURA Y DATOS EXTERNOS BINANCE
            # ============================================================
            st.markdown("---")
            st.subheader("B) Microestructura y datos externos Binance usados en validación")

            col_b1, col_b2 = st.columns(2)

            with col_b1:
                st.markdown("### Microestructura")
                st.write("Spread bps:", market_snapshot.get("spread_bps", "-"))
                st.write("Book imbalance:", market_snapshot.get("book_imbalance", "-"))
                st.write("Buy aggression:", market_snapshot.get("buy_aggression", "-"))
                st.write("Sell aggression:", market_snapshot.get("sell_aggression", "-"))
                st.write("Delta qty:", market_snapshot.get("delta_qty", "-"))
                st.write("Bid wall detected:", market_snapshot.get("bid_wall_detected", "-"))
                st.write("Ask wall detected:", market_snapshot.get("ask_wall_detected", "-"))
                st.write("Vacuum above:", market_snapshot.get("vacuum_above", "-"))
                st.write("Vacuum below:", market_snapshot.get("vacuum_below", "-"))

            with col_b2:
                st.markdown("### Técnicos backend")
                st.write("Close 1m:", market_snapshot.get("close_1m", "-"))
                st.write("EMA20 1m:", market_snapshot.get("ema20_1m", "-"))
                st.write("EMA50 1m:", market_snapshot.get("ema50_1m", "-"))
                st.write("EMA200 1m:", market_snapshot.get("ema200_1m", "-"))
                st.write("ADX 1m:", market_snapshot.get("adx_1m", "-"))
                st.write("Plus DI 1m:", market_snapshot.get("plus_di_1m", "-"))
                st.write("Minus DI 1m:", market_snapshot.get("minus_di_1m", "-"))
                st.write("ATR14 1m:", market_snapshot.get("atr14_1m", "-"))
                st.write("RVOL20 1m:", market_snapshot.get("rvol20_1m", "-"))
                st.write("Impulse ATR 1m:", market_snapshot.get("impulse_atr_1m", "-"))
                st.write("Dist to VWAP % 1m:", market_snapshot.get("dist_to_vwap_pct_1m", "-"))

            st.markdown("### Estructura backend")
            st.write("Last swing high:", structure_snapshot.get("last_swing_high", "-"))
            st.write("Last swing low:", structure_snapshot.get("last_swing_low", "-"))
            st.write("Distance to swing high %:", structure_snapshot.get("distance_to_swing_high_pct", "-"))
            st.write("Distance to swing low %:", structure_snapshot.get("distance_to_swing_low_pct", "-"))
            st.write("Range mode:", structure_snapshot.get("range_mode", "-"))
            st.write("Compression box:", structure_snapshot.get("compression_box", "-"))

            st.markdown("### Steps relacionados con Binance / backend")

            backend_steps = [
                "microstructure_validation",
                "flow_validation",
                "tp_room_validation"
            ]

            for step_name in backend_steps:
                step_data = validation_steps.get(step_name, {})
                if step_data:
                    titulo = f"{step_name} → {step_data.get('status', '-')}"
                    if step_data.get("ok"):
                        st.success(titulo)
                    else:
                        st.error(titulo)
                    st.write("Motivo:", step_data.get("reason", "-"))
                    if step_data.get("details"):
                        with st.expander(f"Detalles de {step_name}", expanded=False):
                            st.json(step_data.get("details", {}))

            if analysis_summary:
                st.markdown("### Conclusión de microestructura / ejecución")
                st.info(f"Ejecución: {analysis_summary.get('execution_quality', '-')}")

            # ============================================================
            # BLOQUE C - MODELO PROBABILÍSTICO Y PROBABILIDAD TP ANTES QUE SL
            # ============================================================
            st.markdown("---")
            st.subheader("C) Modelo probabilístico usado y porcentaje TP antes que SL")

            col_c1, col_c2 = st.columns(2)

            with col_c1:
                st.markdown("### Modelo")
                st.write("Probability model:", validation_block.get("probability_model", "-"))
                st.write("Barrier component:", validation_block.get("barrier_component", "-"))
                st.write("Technical component:", validation_block.get("technical_component", "-"))
                st.write("ML component:", validation_block.get("ml_component", "-"))

            with col_c2:
                st.markdown("### Resultado probabilístico")
                st.metric(
                    "Probabilidad TP antes que SL",
                    f"{round(prob_tp * 100, 2)}%" if isinstance(prob_tp, (float, int)) and prob_tp <= 1 else prob_tp if prob_tp is not None else "-"
                )
                st.write("Confidence:", confidence if confidence is not None else "-")
                st.write("Approve:", approve)
                st.write("Score externo:", score_external if score_external is not None else "-")

            prob_step = validation_steps.get("tp_probability_validation", {})
            if prob_step:
                st.markdown("### Step probabilístico")
                titulo = f"tp_probability_validation → {prob_step.get('status', '-')}"
                if prob_step.get("ok"):
                    st.success(titulo)
                else:
                    st.error(titulo)
                st.write("Motivo:", prob_step.get("reason", "-"))
                if prob_step.get("details"):
                    with st.expander("Detalles del modelo probabilístico", expanded=False):
                        st.json(prob_step.get("details", {}))

            if analysis_trace:
                st.markdown("### Motor de análisis")
                for line in analysis_trace:
                    st.write("•", line)

            if analysis_summary:
                st.markdown("### Conclusión final")
                st.success(f"Conclusión final: {analysis_summary.get('final_conclusion', '-')}")
                st.write(analysis_summary.get("score_comment", ""))

            # ============================================================
            # BLOQUES JSON COMPLETOS
            # ============================================================
            payload_block = data.get("payload", {}) or {}

            st.markdown("---")
            st.subheader("Payload completo de la última alerta")
            st.json(payload_block)

            st.markdown("---")
            st.subheader("Validación completa de la última alerta")
            st.json(validation)

    except Exception as e:
        st.error(f"Error conectando con backend: {e}")
# ============================================================
# CONFIG GENERAL
# ============================================================
SYMBOL = DEFAULT_SYMBOL

TP_BASE = 0.6          # %
SL_BASE = 0.35         # %
RISK_REWARD_WEIGHT = 0.4

CAPITAL_EUR = 170.0
RIESGO_POR_TRADE = 0.01
APALANCAMIENTO = 3.0

TP_REAL = 0.006        # 0.6%
SL_REAL = 0.0035       # 0.35%
COMISION = 0.0008      # 0.08% por lado aprox

BINANCE_BASE_URLS = [
    "https://data-api.binance.vision",
    "https://data.binance.com",
    "https://api.binance.us",
]
LOG_FILE = "signals_log.csv"



st.title("📊 DASHBOARD OPERATIVO BTC - BACKEND ANALÍTICO")

# ============================================================
# UTILS
# ============================================================
def madrid_to_utc_timestamp(fecha_str: str) -> int:
    madrid = pytz.timezone("Europe/Madrid")
    dt_local = madrid.localize(datetime.strptime(fecha_str, "%Y-%m-%d %H:%M"))
    dt_utc = dt_local.astimezone(pytz.utc)
    return int(dt_utc.timestamp() * 1000)


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def rating_score(score: float) -> str:
    if score < 55:
        return "INVÁLIDO"
    elif score < 65:
        return "MARGINAL"
    elif score < 72:
        return "OPERABLE"
    elif score < 82:
        return "BUENO"
    return "ÓPTIMO"


def calcular_trailing(adx: float) -> Optional[float]:
    if adx > 32:
        return 0.15
    elif adx > 26:
        return 0.18
    elif adx > 22:
        return 0.22
    return None
def fetch_backend_json(url: str, timeout: int = 25) -> Dict:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ReadTimeout:
        return {
            "ok": False,
            "error": "TIMEOUT",
            "message": f"El backend no respondió en {timeout} segundos",
            "items": []
        }
    except Exception as e:
        return {
            "ok": False,
            "error": "BACKEND_ERROR",
            "message": str(e),
            "items": []
        }


@st.cache_data(ttl=5, show_spinner=False)
def get_latest_backend_data() -> Dict:
    return fetch_backend_json(BACKEND_LATEST_URL)


@st.cache_data(ttl=5, show_spinner=False)
def get_latest_validation_data() -> Dict:
    return fetch_backend_json(BACKEND_VALIDATION_URL)


@st.cache_data(ttl=5, show_spinner=False)
def get_alerts_history(limit: int = 50) -> Dict:
    return fetch_backend_json(f"{BACKEND_ALERTS_URL}?limit={limit}")
# ============================================================
# INDICADORES PROPIOS (sin pandas_ta)
# ============================================================

# ============================================================
# HELPERS UI - LEYENDAS / EXPLICACIONES
# ============================================================


# ============================================================
# EXPLICACIONES - VALIDACIÓN DE ENTRADA
# ============================================================

# ============================================================
# BINANCE DATA
# ============================================================

# ============================================================
# INDICADORES BASE
# ============================================================

# ============================================================
# LIQUIDITY ENGINE
# ============================================================


# ============================================================
# CONTEXTO / MTF
# ============================================================


# ============================================================
# TRADE ENGINE / RISK ENGINE
# ============================================================

# ============================================================
# LOGGING / BACKTEST
# ============================================================

# ============================================================
# DATA LOAD
# ============================================================
with st.spinner("Cargando datos de mercado..."):
    try:
        raw = obtener_datos_binance(SYMBOL)
    except Exception as e:
        st.error("No se pudo cargar market data desde Binance.")
        st.code(str(e))
        st.info(
            "Esto suele ocurrir cuando Binance bloquea la IP/región del servidor. "
            "La app ya intenta usar endpoints alternativos de market data."
        )
        st.stop()

df_1m = preparar_1m(raw["1m"])
df_5m = preparar_5m_contexto(preparar_tf(raw["5m"]))
df_15m = preparar_tf(raw["15m"])
df_1h = preparar_tf(raw["1h"])

contexto = construir_contexto(df_1m, df_5m, df_15m, df_1h)
liquidity = construir_liquidity_engine(
    df_1m=df_1m,
    atr=contexto["atr"],
    price=contexto["price_1m"]
)

# ============================================================
# SIDEBAR
# ============================================================
market_sidebar_state = render_market_sidebar(SYMBOL)
symbol = market_sidebar_state["symbol"]

# ============================================================
# HEADER METRICS
# ============================================================
col1, col2, col3, col4 = st.columns(4)
col1.metric("Precio 1m", f"{contexto['price_1m']:.2f}")
col2.metric("FASE 5M", contexto["fase"])
col3.metric("ADX 5M", f"{contexto['adx_5m']:.2f}")
col4.metric("Probabilidad base", f"{contexto['probabilidad']:.1f}%")

# ============================================================
# SEÑAL ACTUAL
# ============================================================
st.subheader("Señal Actual del Entorno")

trade_levels_long = compute_trade_levels(
    entrada=contexto["price_1m"],
    direccion="LONG",
    df_5m=df_5m,
    adx_5m=contexto["adx_5m"]
)

trade_levels_short = compute_trade_levels(
    entrada=contexto["price_1m"],
    direccion="SHORT",
    df_5m=df_5m,
    adx_5m=contexto["adx_5m"]
)

if contexto["long_valido"] and not contexto["short_valido"]:
    st.success("🚀 LONG VÁLIDO")
    st.write("TP:", round(trade_levels_long["tp"], 2))
    st.write("SL:", round(trade_levels_long["sl"], 2))
    log_signal("LONG", contexto["probabilidad"], contexto["fase"], contexto["adx_5m"], contexto["rsi_1m"])
elif contexto["short_valido"] and not contexto["long_valido"]:
    st.error("🔻 SHORT VÁLIDO")
    st.write("TP:", round(trade_levels_short["tp"], 2))
    st.write("SL:", round(trade_levels_short["sl"], 2))
    log_signal("SHORT", contexto["probabilidad"], contexto["fase"], contexto["adx_5m"], contexto["rsi_1m"])
elif contexto["long_valido"] and contexto["short_valido"]:
    st.warning("⚠ Contexto ambiguo. Esperar confirmación externa del trigger.")
else:
    st.warning("⏳ ESPERAR")

# ============================================================
# TABS
# ============================================================
tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Monitor Backend",
    "Contexto",
    "Liquidez",
    "Validación MTF",
    "Evaluador de Trade",
    "Backtest / Histórico"
])

#  VISUALIZACION HITORICO ALERTAS

# ============================================================
# TAB 0 - MONITOR BACKEND
# ============================================================
with tab0:
    render_backend_monitor_tab()

# ============================================================
# TAB 1 - CONTEXTO
# ============================================================
with tab1:
    render_context_tab(contexto)

# ============================================================
# TAB 2 - LIQUIDEZ
# ============================================================
# ============================================================
# TAB 2 - LIQUIDEZ
# ============================================================
with tab2:
    render_liquidity_tab(contexto, liquidity)

# ============================================================
# TAB 3 - VALIDACIÓN MTF
# ============================================================
with tab3:
    render_mtf_tab(
        df_1m=df_1m,
        df_5m=df_5m,
        df_15m=df_15m,
        df_1h=df_1h,
    )

# ============================================================
# TAB 4 - EVALUADOR DE TRADE
# ============================================================
with tab4:
    render_trade_evaluator_tab(
        contexto=contexto,
        liquidity=liquidity,
        df_5m=df_5m,
    )

# ============================================================
# TAB 5 - BACKTEST / HISTÓRICO
# ============================================================
with tab5:
    render_backtest_tab(df_1m)