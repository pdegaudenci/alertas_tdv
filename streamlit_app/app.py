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
auto_refresh = st.sidebar.checkbox("Auto refresh backend", value=True)
refresh_seconds = st.sidebar.slider("Refresh backend cada segundos", 5, 60, 10)

if auto_refresh:
    st.sidebar.info(f"Auto refresh activo cada {refresh_seconds}s")
    st_autorefresh(
        interval=refresh_seconds * 1000,
        key="backend_auto_refresh"
    )
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
st.sidebar.header("Configuración")
symbol = st.sidebar.text_input("Símbolo", value=SYMBOL, disabled=True)
st.sidebar.write("Actualización automática cada 60s por cache.")
if st.sidebar.button("Actualizar mercado ahora"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.markdown("---")
st.sidebar.subheader("Fuente de datos")
st.sidebar.write("Endpoints probados en orden:")
for endpoint in BINANCE_BASE_URLS:
    st.sidebar.code(endpoint, language=None)
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
# TAB 0 - MONITOR BACKEND / HISTÓRICO ALERTAS
# ============================================================

with tab0:
    st.subheader("📡 Monitor de alertas procesadas por Vercel")

    colb1, colb2 = st.columns([1, 1])

    with colb1:
        if st.button("Recargar backend ahora"):
            st.cache_data.clear()
            st.rerun()

    with colb2:
        history_limit = st.selectbox(
            "Número de alertas a mostrar",
            [10, 20, 50, 100],
            index=2
        )

    try:
        latest_response = get_latest_backend_data()
        latest_data = unwrap_latest_response(latest_response)

        latest_validation = get_latest_validation_data()
        alerts_history = get_alerts_history_supabase(history_limit)

        st.success("Backend conectado correctamente")

        # ============================================================
        # ÚLTIMA ALERTA - RESUMEN
        # ============================================================

        if latest_data.get("ok"):
            st.markdown("## Última alerta recibida")

            latest_summary = extract_latest_alert_summary(latest_data)

            validation = latest_summary.get("validation", {}) or {}
            validation_block = extract_validation_block(latest_data)
            validation_metrics = build_validation_metrics(validation_block)
            validation_sections = extract_validation_sections(validation_block)

            payload_block = latest_summary.get("payload", {}) or {}

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Símbolo", latest_summary.get("symbol", "-"))
            c2.metric("Side", str(latest_summary.get("side", "-")).upper())
            c3.metric("Evento", latest_summary.get("event", "-"))
            c4.metric("TF", latest_summary.get("timeframe", "-"))

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Precio", latest_summary.get("price", "-"))
            c6.metric("Phase", latest_summary.get("phase", "-"))
            c7.metric("Regime", latest_summary.get("regime", "-"))
            c8.metric("Quality", latest_summary.get("quality_score", "-"))

            st.write("Setup:", latest_summary.get("setup", "-"))
            st.write("Phase 5m:", latest_summary.get("phase_5m", "-"))
            st.write("Strength 5m:", latest_summary.get("strength_5m", "-"))
            st.write("Recibida:", latest_summary.get("received_at", "-"))
            st.write("Trace ID:", latest_summary.get("trace_id", "-"))
            st.write("Message type:", latest_summary.get("message_type", "-"))
            st.write("Event UID:", latest_summary.get("event_uid", "-"))

            # ============================================================
            # RESULTADO DE VALIDACIÓN
            # ============================================================

            st.markdown("---")
            st.markdown("## Resultado de validación")

            approve = validation_metrics["approve"]
            confidence = validation_metrics["confidence"]
            prob_tp = validation_metrics["prob_tp"]
            score_external = validation_metrics["score_external"]

            v1, v2, v3, v4 = st.columns(4)
            v1.metric("Approve", validation_metrics["approve_label"])
            v2.metric("Confidence", validation_metrics["confidence_label"])
            v3.metric("Prob TP antes SL", validation_metrics["prob_tp_label"])
            v4.metric("Score externo", validation_metrics["score_external_label"])

            approve_message = get_approve_status_message(approve)

            if approve_message["status"] == "success":
                st.success(approve_message["message"])
            elif approve_message["status"] == "error":
                st.error(approve_message["message"])
            else:
                st.warning(approve_message["message"])

            st.write("TP:", validation_metrics["tp"])
            st.write("SL:", validation_metrics["sl"])
            st.write("RR:", validation_metrics["rr"])

            reasons = validation_sections["reasons"]
            penalties = validation_sections["penalties"]

            colr, colp = st.columns(2)

            with colr:
                st.markdown("### Razones a favor")
                if reasons:
                    for item in reasons:
                        st.success(f"✔ {item}")
                else:
                    st.info("Sin razones registradas")

            with colp:
                st.markdown("### Penalizaciones")
                if penalties:
                    for item in penalties:
                        st.error(f"✖ {item}")
                else:
                    st.info("Sin penalizaciones registradas")

            # ============================================================
            # VALIDATION STEPS
            # ============================================================

            validation_steps = validation_sections["validation_steps"]

            if validation_steps:
                st.markdown("---")
                st.markdown("## Validation Steps")

                for step_name, step_data in validation_steps.items():
                    if not isinstance(step_data, dict):
                        continue

                    titulo = f"{step_name} → {step_data.get('status', '-')}"

                    if step_data.get("ok"):
                        st.success(titulo)
                    else:
                        st.error(titulo)

                    st.write("Motivo:", step_data.get("reason", "-"))

                    if step_data.get("details"):
                        with st.expander(f"Detalles de {step_name}", expanded=False):
                            st.json(step_data.get("details", {}))

            # ============================================================
            # ANALYSIS TRACE / SUMMARY
            # ============================================================

            analysis_trace = validation_sections["analysis_trace"]
            analysis_summary = validation_sections["analysis_summary"]

            if analysis_trace:
                st.markdown("---")
                st.markdown("## Motor de análisis")

                for line in analysis_trace:
                    st.write("•", line)

            if analysis_summary:
                st.markdown("---")
                st.markdown("## Resumen del análisis")

                st.info(f"Contexto: {analysis_summary.get('market_context', '-')}")
                st.info(f"Ejecución: {analysis_summary.get('execution_quality', '-')}")
                st.info(f"Riesgo: {analysis_summary.get('risk_reading', '-')}")
                st.success(f"Conclusión final: {analysis_summary.get('final_conclusion', '-')}")
                st.write(analysis_summary.get("score_comment", ""))

            # ============================================================
            # SNAPSHOT DE MERCADO
            # ============================================================

            market_snapshot = validation_sections["market_snapshot"]

            if market_snapshot:
                st.markdown("---")
                st.markdown("### Snapshot de mercado usado por backend")

                snap_df = pd.DataFrame([market_snapshot])
                st.dataframe(snap_df, use_container_width=True)

            # ============================================================
            # SNAPSHOT ESTRUCTURAL
            # ============================================================

            structure_snapshot = validation_sections["structure_snapshot"]

            if structure_snapshot:
                st.markdown("### Snapshot estructural")
                st.json(structure_snapshot)

            # ============================================================
            # ALERT REUSED / CONTEXTO REUTILIZADO
            # ============================================================

            alert_reused = validation_sections["alert_reused"]

            if alert_reused:
                st.markdown("### Datos reutilizados desde alerta Pine")
                st.json(alert_reused)

            # ============================================================
            # PAYLOADS COMPLETOS
            # ============================================================

            st.markdown("---")
            st.markdown("## Payload completo de la última alerta")
            st.json(payload_block)

            st.markdown("---")
            st.markdown("## Validación completa de la última alerta")
            st.json(validation)

            with st.expander("Ver objeto completo /api/latest", expanded=False):
                st.json(latest_data)

            with st.expander("Ver objeto completo /api/validation/latest", expanded=False):
                st.json(latest_validation)

        else:
            st.warning("Todavía no hay última alerta válida en el backend.")
            with st.expander("Respuesta recibida desde /api/latest", expanded=False):
                st.json(latest_data)

        # ============================================================
        # HISTÓRICO RESUMIDO
        # ============================================================

        st.markdown("---")
        st.markdown("## Histórico resumido de alertas procesadas")

        items = alerts_history.get("items", []) if isinstance(alerts_history, dict) else []

        if items:
            df_alerts = build_alert_history_dataframe(items)
            st.dataframe(df_alerts, use_container_width=True)

            st.markdown("### Detalle expandible")

            for idx, item in enumerate(items[:20]):
                titulo = build_alert_expander_title(idx, item)

                with st.expander(titulo, expanded=False):
                    detail = extract_alert_detail(item)

                    st.write("Setup ID:", detail.get("setup_id"))
                    st.write("Status:", detail.get("status"))
                    st.write("Phase:", detail.get("phase"))
                    st.write("Regime:", detail.get("regime"))
                    st.write("Dir state:", detail.get("dir_state"))
                    st.write("Mov state:", detail.get("mov_state"))
                    st.write("Liq state:", detail.get("liq_state"))
                    st.write("HTF phase:", detail.get("htf_phase"))
                    st.write("Trigger alignment:", detail.get("trigger_alignment"))
                    st.write("Spread bps:", detail.get("spread_bps"))
                    st.write("Book imbalance:", detail.get("book_imbalance"))

                    st.markdown("#### Normalized payload")
                    st.json(detail.get("normalized_payload", {}))

                    st.markdown("#### Technical state")
                    st.json(detail.get("technical_state", {}))

                    st.markdown("#### Microstructure state")
                    st.json(detail.get("microstructure_state", {}))

                    st.markdown("#### Raw payload")
                    st.json(detail.get("raw_payload", {}))

        else:
            st.info("No hay histórico disponible todavía")

            if isinstance(alerts_history, dict) and not alerts_history.get("ok", True):
                with st.expander("Respuesta de error del histórico Supabase", expanded=False):
                    st.json(alerts_history)

    except Exception as e:
        st.error(f"Error conectando con backend: {e}")    
# ============================================================
# TAB 1 - CONTEXTO
# ============================================================
with tab1:
    st.subheader("🌍 Régimen de Mercado")
    st.write("Estado actual:", contexto["market_regime"])

    if contexto["market_regime"] == "RANGO":
        st.error("Mercado lateral — alto riesgo de stops")
    elif contexto["market_regime"] == "TRANSICIÓN":
        st.warning("Mercado inestable")
    elif contexto["market_regime"] == "EXPANSIÓN":
        st.success("Movimiento limpio probable")
    elif contexto["market_regime"] == "TENDENCIA":
        st.success("Alta continuidad direccional")
    else:
        st.info("Contexto neutro")

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("RSI 1m", f"{contexto['rsi_1m']:.2f}")
    c2.metric("ROC 1m", f"{contexto['roc']:.4f}")
    c3.metric("ATR actual", f"{contexto['atr']:.2f}")

    st.subheader("🧠 Contexto de Mercado")
    st.write("Precio vs VWAP:", "Encima (alcista)" if contexto["above_vwap"] else "Debajo (bajista)")
    st.write("Precio vs EMA200 5m:", "Encima" if contexto["above_ema200"] else "Debajo")
    st.write("Stack EMAs 1m:", "Alcista" if contexto["ema_bullish_stack"] else "Bajista" if contexto["ema_bearish_stack"] else "Mixto")
    st.write("No agotamiento:", contexto["no_agotamiento"])
    st.write("Espacio LONG:", contexto["espacio_long"])
    st.write("Espacio SHORT:", contexto["espacio_short"])

    st.subheader("🧱 Compresión de Volatilidad")
    st.write("Bollinger Width:", round(contexto["bb_width"], 4))

    if contexto["bb_width"] < 0.002:
        st.error("Alta compresión — NO OPERAR")
    elif contexto["bb_width"] < 0.004:
        st.warning("Mercado apretado")
    else:
        st.success("Volatilidad suficiente")

    st.subheader("📐 Valor Esperado del Trade (base)")
    st.write("EV:", round(contexto["EV"], 4), "%")

    if contexto["EV"] > 0.12:
        st.success("Ventaja matemática clara")
    elif contexto["EV"] > 0:
        st.info("Trade ligeramente favorable")
    else:
        st.error("Trade con esperanza negativa — evitar")

# ============================================================
# TAB 2 - LIQUIDEZ
# ============================================================
with tab2:
    st.subheader("💧 Liquidez cercana")

    dist_up_pct = liquidity["dist_up_pct"]
    dist_down_pct = liquidity["dist_down_pct"]

    micro_risk = False
    if dist_up_pct is not None and dist_up_pct < 0.0025:
        st.warning("Stops muy cerca arriba → posible sweep alcista inmediato")
        micro_risk = True
    if dist_down_pct is not None and dist_down_pct < 0.0025:
        st.warning("Stops muy cerca abajo → posible sweep bajista inmediato")
        micro_risk = True
    if not micro_risk:
        st.success("No hay liquidez inmediata peligrosa")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if liquidity["nearest_resistance"] is None:
            st.metric("Liquidez arriba (ATR)", "∞")
            st.success("No existe liquidez por encima → price discovery alcista")
        else:
            dist_up_atr = (liquidity["nearest_resistance"] - contexto["price_1m"]) / contexto["atr"]
            st.metric("Liquidez arriba (ATR)", round(dist_up_atr, 2))
            if dist_up_atr < 0.7:
                st.error("Liquidez MUY cercana arriba → probable sweep alcista")
            elif dist_up_atr < 1.2:
                st.warning("Zona de riesgo arriba")
            else:
                st.success("Espacio limpio arriba")

    with col2:
        if liquidity["nearest_support"] is None:
            st.metric("Liquidez abajo (ATR)", "∞")
            st.success("No existe liquidez por debajo → price discovery bajista")
        else:
            dist_down_atr = (contexto["price_1m"] - liquidity["nearest_support"]) / contexto["atr"]
            st.metric("Liquidez abajo (ATR)", round(dist_down_atr, 2))
            if dist_down_atr < 0.7:
                st.error("Liquidez MUY cercana abajo → probable sweep bajista")
            elif dist_down_atr < 1.2:
                st.warning("Zona de riesgo abajo")
            else:
                st.success("Espacio limpio abajo")

    st.markdown("### 🧲 Intención Probable del Mercado")
    if liquidity["liquidity_attraction"] == "UP":
        st.info("El mercado probablemente buscará stops de SHORTS primero")
    elif liquidity["liquidity_attraction"] == "DOWN":
        st.info("El mercado probablemente buscará stops de LONGS primero")
    else:
        st.write("No hay sesgo claro de liquidez")

    st.markdown("### 🧱 Fuerza Estructural")
    if liquidity["resistance_zones"]:
        st.write("🔴 Resistencias institucionales:")
        for zmin, zmax in liquidity["resistance_zones"]:
            distancia = ((zmin - contexto["price_1m"]) / contexto["price_1m"]) * 100
            st.error(f"Zona: {round(zmin, 2)} → {round(zmax, 2)} | Distancia: {round(distancia, 3)}%")
    else:
        st.success("No hay resistencias institucionales cercanas")

    if liquidity["support_zones"]:
        st.write("🟢 Soportes institucionales:")
        for zmin, zmax in liquidity["support_zones"]:
            distancia = ((contexto["price_1m"] - zmax) / contexto["price_1m"]) * 100
            st.success(f"Zona: {round(zmin, 2)} → {round(zmax, 2)} | Distancia: {round(distancia, 3)}%")
    else:
        st.success("No hay soportes institucionales cercanos")

    st.markdown("### ⚠ Riesgo de Liquidez")
    st.metric("Market Structure Risk", f"{liquidity['market_lrs']:.1f}/80")

    if liquidity["market_lrs"] < 20:
        st.success("Bajo riesgo de barrida")
    elif liquidity["market_lrs"] < 40:
        st.info("Riesgo moderado")
    elif liquidity["market_lrs"] < 60:
        st.warning("Alto riesgo")
    else:
        st.error("Muy alto riesgo")

    st.markdown("### 🧠 Estado Operativo del Mercado")
    if liquidity["market_clean"]:
        st.success("Mercado relativamente limpio → continuidad posible")
    else:
        st.error("Mercado sucio → alta probabilidad de barrida antes de continuar")

# ============================================================
# TAB 3 - VALIDACIÓN MTF
# ============================================================
with tab3:
    st.subheader("🧠 Validación MTF")

    for direccion in ["LONG", "SHORT"]:
        st.markdown(f"## {direccion}")
        mtf_valido, detalle = evaluar_mtf(direccion, df_1h, df_15m, df_5m, df_1m)

        if mtf_valido:
            st.success(f"{direccion} VÁLIDO")
        else:
            st.error(f"{direccion} INVÁLIDO")

        ema9_5m = df_5m["ema9"].iloc[-1]
        ema20_5m = df_5m["ema20"].iloc[-1]
        ema50_5m = df_5m["ema50"].iloc[-1]
        price5m = df_5m["close"].iloc[-1]

        emas_ok, d1, d2 = emas_abiertas_5m(
            direccion,
            ema9_5m,
            ema20_5m,
            ema50_5m,
            price5m
        )

        ca, cb, cc = st.columns(3)
        ca.metric("EMA9-EMA20 distancia", f"{d1 * 100:.3f}%")
        cb.metric("EMA20-EMA50 distancia", f"{d2 * 100:.3f}%")
        cc.metric("EMAs abiertas", "SI" if emas_ok else "NO")

        for tf, (valido_tf, checks) in detalle.items():
            st.subheader(f"{tf} ({'VÁLIDO' if valido_tf else 'INVÁLIDO'})")
            for c in checks:
                if c["ok"]:
                    st.success(f"✔ {c['texto']} : {c['valor']}")
                else:
                    st.error(f"✖ {c['texto']} : {c['valor']}")

        st.markdown("---")

# ============================================================
# TAB 4 - EVALUADOR DE TRADE
# ============================================================
with tab4:
    st.title("🧠 Evaluador Integral de Trade")
    st.write("Mínimo recomendado para operar: 65%")

    with st.form("trade_eval"):
        entrada = st.number_input("Precio de entrada", value=float(contexto["price_1m"]), step=0.1)
        direccion = st.selectbox("Dirección", ["LONG", "SHORT"])
        evaluar = st.form_submit_button("Evaluar Trade")

    if evaluar:
        st.markdown("---")
        st.header("Análisis del Trade")

        score_market = 0
        motivos = []

        if contexto["adx_5m"] > 25:
            score_market += 30
            motivos.append("Mercado con fuerza (ADX>25)")
        elif contexto["adx_5m"] > 22:
            score_market += 20
            motivos.append("Impulso moderado")
        else:
            motivos.append("Mercado débil (ADX bajo)")

        if contexto["fase"] == "RANGO":
            motivos.append("Mercado en rango")
        else:
            score_market += 20
            motivos.append(f"Fase {contexto['fase']}")

        if contexto["vela_extendida"]:
            motivos.append("Vela 1m extendida (posible clímax)")
        if contexto["adx_cayendo"]:
            motivos.append("ADX cayendo (pérdida de fuerza)")

        prob_mercado = min(score_market, 90)

        st.subheader("1) Condición del Mercado")
        st.progress(prob_mercado / 100)
        st.write(f"Probabilidad entorno favorable: {prob_mercado}%")

        with st.expander("ℹ️ Cómo se calculó este porcentaje", expanded=False):
            st.write(explicacion_prob_mercado(prob_mercado, score_market, contexto))

        # -------- Leyendas explicativas de los factores activos --------
        if contexto["adx_5m"] > 25:
            render_info_item(
                "• Mercado con fuerza (ADX > 25)",
                explicacion_mercado_fuerza(),
                estado="success"
            )
        elif contexto["adx_5m"] > 22:
            render_info_item(
                "• Impulso moderado (ADX > 22)",
                """
**Impulso moderado**

El ADX está por encima del umbral mínimo de debilidad, pero aún no habla de una tendencia muy potente.
Esto sugiere que el mercado puede moverse, aunque con menos autoridad que en un escenario de ADX > 25.
""".strip(),
                estado="info"
            )
        else:
            render_info_item(
                "• Mercado débil (ADX bajo)",
                """
**Mercado débil**

Un ADX bajo indica que el precio no está desarrollando una tendencia con suficiente intensidad.
Eso suele traducirse en:
- menos continuidad,
- más ruido,
- más riesgo de falsas señales.
""".strip(),
                estado="warning"
            )

        if contexto["fase"] == "RANGO":
            render_info_item(
                f"• Fase {contexto['fase']}",
                explicacion_fase(contexto["fase"]),
                estado="warning"
            )
        else:
            render_info_item(
                f"• Fase {contexto['fase']}",
                explicacion_fase(contexto["fase"]),
                estado="success"
            )

        if contexto["vela_extendida"]:
            render_info_item(
                "• Vela 1m extendida (posible clímax)",
                explicacion_climax(),
                estado="warning"
            )

        if contexto["adx_cayendo"]:
            render_info_item(
                "• ADX cayendo (pérdida de fuerza)",
                explicacion_adx_cayendo(),
                estado="warning"
            )

        if not contexto["vela_extendida"] and not contexto["adx_cayendo"]:
            st.success("• No hay señales claras de agotamiento en este momento")

        score_entry = 50
        debug_entry = []

        if direccion == "LONG":
            if contexto["roc"] > 0.04:
                score_entry += 12
                debug_entry.append(("Momentum inmediato alcista", f"{contexto['roc']:.4f}", "+12"))
            elif contexto["roc"] < 0:
                score_entry -= 12
                debug_entry.append(("Momentum contrario", f"{contexto['roc']:.4f}", "-12"))
        else:
            if contexto["roc"] < -0.04:
                score_entry += 12
                debug_entry.append(("Momentum inmediato bajista", f"{contexto['roc']:.4f}", "+12"))
            elif contexto["roc"] > 0:
                score_entry -= 12
                debug_entry.append(("Momentum contrario", f"{contexto['roc']:.4f}", "-12"))

        if direccion == "LONG":
            if 52 <= contexto["rsi_1m"] <= 68:
                score_entry += 8
                debug_entry.append(("RSI saludable", f"{contexto['rsi_1m']:.1f}", "+8"))
            elif contexto["rsi_1m"] > 72:
                score_entry -= 10
                debug_entry.append(("RSI sobreextendido", f"{contexto['rsi_1m']:.1f}", "-10"))
        else:
            if 32 <= contexto["rsi_1m"] <= 48:
                score_entry += 8
                debug_entry.append(("RSI saludable", f"{contexto['rsi_1m']:.1f}", "+8"))
            elif contexto["rsi_1m"] < 28:
                score_entry -= 10
                debug_entry.append(("RSI sobreextendido", f"{contexto['rsi_1m']:.1f}", "-10"))

        if direccion == "LONG" and contexto["ema_bullish_stack"]:
            score_entry += 10
            debug_entry.append(("Microtendencia a favor", "EMA20>EMA50", "+10"))
        elif direccion == "SHORT" and contexto["ema_bearish_stack"]:
            score_entry += 10
            debug_entry.append(("Microtendencia a favor", "EMA20<EMA50", "+10"))
        else:
            score_entry -= 12
            debug_entry.append(("Microtendencia contraria", "EMA stack", "-12"))

        if (direccion == "LONG" and contexto["above_vwap"]) or (direccion == "SHORT" and not contexto["above_vwap"]):
            score_entry += 10
            debug_entry.append(("Precio control institucional", "VWAP", "+10"))
        else:
            score_entry -= 14
            debug_entry.append(("Contra VWAP", "VWAP", "-14"))

        if 0.5 <= contexto["atr_ratio"] <= 1.3:
            score_entry += 10
            debug_entry.append(("Energía suficiente", f"{contexto['atr_ratio']:.2f}", "+10"))
        elif contexto["atr_ratio"] < 0.35:
            score_entry -= 18
            debug_entry.append(("Movimiento sin energía", f"{contexto['atr_ratio']:.2f}", "-18"))

        if contexto["bb_width"] < 0.002:
            score_entry -= 15
            debug_entry.append(("Compresión extrema", f"{contexto['bb_width']:.4f}", "-15"))

        prob_entry = max(15, min(score_entry, 95))

        
        st.subheader("2) Validación de Entrada")
        st.progress(prob_entry / 100)
        st.write(f"Calidad de la entrada: {prob_entry}%")

        with st.expander("ℹ️ Cómo se calculó la calidad de entrada", expanded=False):
            st.write(explicacion_prob_entry(prob_entry, score_entry, direccion))

        for nombre, valor, impacto in debug_entry:

            positivo = "-" not in impacto

            # ---------------------------------
            # MENSAJE VISUAL
            # ---------------------------------
            texto = f"{nombre} | Valor: {valor} | Impacto: {impacto}"

            if positivo:
                st.success(f"✔ {texto}")
            else:
                st.error(f"✖ {texto}")

            # ---------------------------------
            # EXPLICACIÓN SEGÚN FACTOR
            # ---------------------------------
            explicacion = None

            if "Momentum inmediato bajista" in nombre:
                explicacion = explicacion_momentum_bajista()

            elif "Momentum inmediato alcista" in nombre:
                explicacion = explicacion_momentum_alcista()

            elif "RSI saludable" in nombre:
                explicacion = explicacion_rsi_saludable(direccion)

            elif "Microtendencia contraria" in nombre:
                explicacion = explicacion_microtendencia_contraria()

            elif "Microtendencia a favor" in nombre:
                explicacion = """
**Microtendencia a favor**

Las EMAs rápidas están alineadas con la dirección del trade.

Esto mejora:
- timing,
- continuidad,
- estructura inmediata.
""".strip()

            elif "Precio control institucional" in nombre:
                explicacion = explicacion_vwap()

            elif "Contra VWAP" in nombre:
                explicacion = """
**Contra VWAP**

La operación va en contra del sesgo institucional actual.

Eso suele empeorar:
- continuidad,
- timing,
- probabilidad de TP.
""".strip()

            elif "Movimiento sin energía" in nombre:
                explicacion = explicacion_sin_energia()

            elif "Energía suficiente" in nombre:
                explicacion = """
**Energía suficiente**

La volatilidad actual (ATR) es adecuada para intentar alcanzar el TP planteado.
""".strip()

            elif "Compresión extrema" in nombre:
                explicacion = explicacion_compresion_extrema()

            elif "RSI sobreextendido" in nombre:
                explicacion = """
**RSI sobreextendido**

El movimiento puede estar demasiado avanzado.
Entrar aquí aumenta el riesgo de llegar tarde.
""".strip()

            elif "Momentum contrario" in nombre:
                explicacion = """
**Momentum contrario**

La velocidad reciente del precio va en contra de la dirección elegida.
""".strip()

            if explicacion:
                with st.expander(f"ℹ️ Ver explicación: {nombre}", expanded=False):
                    st.write(explicacion)

        niveles = compute_trade_levels(entrada, direccion, df_5m, contexto["adx_5m"])
        st.subheader("3) Gestión del Trade")

        c1, c2, c3 = st.columns(3)
        c1.metric("TP objetivo", round(niveles["tp"], 2))
        c2.metric("SL controlado", round(niveles["sl"], 2))
        c3.metric("Break Even", round(niveles["be"], 2))

        if niveles["trailing"] is not None:
            st.success(f"Trailing activo: {niveles['trailing']}%")
        else:
            st.warning("Trailing desactivado")

        lrs_info = liquidity_risk_explained(
            direccion=direccion,
            price=entrada,
            atr=contexto["atr"],
            nearest_resistance=liquidity["nearest_resistance"],
            nearest_support=liquidity["nearest_support"],
            liquidity_attraction=liquidity["liquidity_attraction"],
            strong_resistances=liquidity["strong_resistances"],
            strong_supports=liquidity["strong_supports"]
        )

        prob_tp, debug_info = probabilidad_tp_real(
            direccion=direccion,
            prob_mercado=prob_mercado,
            prob_entry=prob_entry,
            rr=niveles["rr"],
            atr_ratio=contexto["atr_ratio"],
            adx=contexto["adx_5m"],
            rsi=contexto["rsi_1m"],
            lrs=lrs_info["score"],
            market_regime=contexto["market_regime"],
            liquidity_attraction=liquidity["liquidity_attraction"],
            ema_stack=contexto["ema_bullish_stack"] if direccion == "LONG" else contexto["ema_bearish_stack"],
            above_vwap=contexto["above_vwap"]
        )

        prob_profit = probabilidad_rentable(prob_tp, niveles["rr"])

        st.write(f"Riesgo real: {niveles['risk_pct']:.3f}% ({niveles['risk_label']})")
        st.write(f"Beneficio potencial: {niveles['reward_pct']:.3f}% ({niveles['reward_label']})")
        st.write(f"R:R real: {niveles['rr']:.2f} ({niveles['rr_label']})")

        st.subheader("Probabilidad real de alcanzar TP")
        st.progress(prob_tp / 100)
        st.write(f"{prob_tp:.1f}%")

        with st.expander("ℹ️ Cómo se calculó la probabilidad de TP", expanded=False):
            st.write(
                explicacion_prob_tp_real(
                    prob_tp=prob_tp,
                    prob_mercado=prob_mercado,
                    prob_entry=prob_entry,
                    rr=niveles["rr"],
                    atr_ratio=contexto["atr_ratio"],
                    adx=contexto["adx_5m"],
                    rsi=contexto["rsi_1m"],
                    lrs=lrs_info["score"],
                    market_regime=contexto["market_regime"],
                    liquidity_attraction=liquidity["liquidity_attraction"]
                )
        )
        st.subheader("Probabilidad de rentabilidad")
        st.progress(prob_profit / 100)
        st.write(f"{prob_profit:.1f}%")

        with st.expander("ℹ️ Cómo se calculó la probabilidad de rentabilidad", expanded=False):
            st.write(
                explicacion_prob_rentable(
                    prob_profit=prob_profit,
                    prob_tp=prob_tp,
                    rr=niveles["rr"]
                )
            )
        base_score = (prob_mercado * 0.55 + prob_entry * 0.45)
        liquidity_penalty = lrs_info["score"] * 0.35
        final_score = max(5, min(base_score - liquidity_penalty, 95))
        rating = rating_score(final_score)

        st.subheader("Calidad Técnica del Setup")
        st.write(f"Score total: {final_score:.1f}% — {rating}")

        with st.expander("ℹ️ Cómo se calculó la calidad técnica del setup", expanded=False):
            st.write(
                explicacion_calidad_setup(
                    final_score=final_score,
                    rating=rating,
                    prob_mercado=prob_mercado,
                    prob_entry=prob_entry,
                    lrs_score=lrs_info["score"]
                )
            )

        permiso_operar = final_score >= 65
        alta_tp = prob_tp >= 60
        alta_rentable = prob_profit >= 55

        st.subheader("Decisión Final")
        if not permiso_operar:
            st.error("⛔ MERCADO NO APTO PARA OPERAR")
            st.write("El problema principal es el contexto.")
        else:
            if alta_tp and alta_rentable:
                st.success("🚀 TRADE IDEAL")
            elif alta_tp and not alta_rentable:
                st.warning("⚠ Mucho acierto, poca rentabilidad")
            elif not alta_tp and alta_rentable:
                st.info("💼 Trade profesional (asimetría positiva)")
            else:
                st.error("⛔ No operar")

        st.subheader("Motor de decisión (debug)")
        for nombre, valor, impacto in debug_info:
            if "-" in impacto:
                st.error(f"✖ {nombre} | Valor: {valor} | Impacto: {impacto}")
            elif "+" in impacto:
                st.success(f"✔ {nombre} | Valor: {valor} | Impacto: {impacto}")
            else:
                st.info(f"• {nombre} | Valor: {valor}")

        st.subheader("Liquidity Risk Analysis")
        st.metric(
            "Trade Liquidity Risk",
            f"{lrs_info['score']}/80 ({lrs_info['label']})"
        )

        for item in lrs_info["debug"]:
            st.write("•", item)

        st.subheader("Gestión de la Posición")
        datos_posicion = calcular_posicion_real(entrada, niveles["sl"], niveles["tp"])

        if datos_posicion:
            p1, p2, p3 = st.columns(3)
            p1.metric("Tamaño posición", f"{datos_posicion['posicion']:.0f} €")
            p2.metric("Margen necesario", f"{datos_posicion['margen']:.2f} €")
            p3.metric("Riesgo real", f"{datos_posicion['riesgo']:.2f} €")

            st.write(f"Ganancia neta estimada: **{datos_posicion['beneficio']:.2f} €**")
            st.write(f"Comisiones aproximadas: {datos_posicion['comisiones']:.2f} €")
            st.write(f"Pérdida máxima: **-{datos_posicion['riesgo']:.2f} €**")

            rr_real = datos_posicion["beneficio"] / datos_posicion["riesgo"] if datos_posicion["riesgo"] > 0 else 0

            if rr_real >= 1.4:
                st.success("El trade es matemáticamente rentable")
            elif rr_real >= 1.1:
                st.warning("Trade aceptable pero justo")
            else:
                st.error("Trade NO rentable → NO operar")
        else:
            st.error("No se puede calcular el tamaño de posición")

# ============================================================
# TAB 5 - BACKTEST / HISTÓRICO
# ============================================================
with tab5:
    st.subheader("Backtest rápido 1M")

    wins_l, losses_l, winrate_l, final_capital_l = backtest(df_1m, "long")
    wins_s, losses_s, winrate_s, final_capital_s = backtest(df_1m, "short")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### LONG")
        st.write("Wins:", wins_l)
        st.write("Losses:", losses_l)
        st.write("Winrate:", round(winrate_l, 2), "%")
        st.write("Capital final simulado:", round(final_capital_l, 2))

    with c2:
        st.markdown("### SHORT")
        st.write("Wins:", wins_s)
        st.write("Losses:", losses_s)
        st.write("Winrate:", round(winrate_s, 2), "%")
        st.write("Capital final simulado:", round(final_capital_s, 2))

    st.markdown("---")
    st.subheader("Probabilidad histórica por condiciones similares")
    hist_long = probabilidad_historica(df_1m, "LONG")
    hist_short = probabilidad_historica(df_1m, "SHORT")

    st.write(f"LONG histórico: {hist_long:.2f}%")
    st.write(f"SHORT histórico: {hist_short:.2f}%")
