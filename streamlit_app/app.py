"""
App principal del panel Streamlit.

Responsabilidad:
- Configurar la página.
- Cargar datos de mercado.
- Preparar dataframes.
- Construir contexto y liquidez.
- Renderizar sidebar, header, señal actual y tabs.

Este archivo NO debe contener:
- lógica pesada de indicadores,
- cálculos de liquidez,
- backtest,
- validación MTF,
- textos largos de explicación,
- transformación de payloads backend,
- llamadas HTTP directas al backend.

La lógica fue separada en capas:
- core/
- utils/
- clients/
- services/
- components/
- views/
"""

import time

import streamlit as st

from core.config import (
    PAGE_TITLE,
    PAGE_ICON,
    PAGE_LAYOUT,
    DEFAULT_SYMBOL,
)

from services.market_data_service import obtener_datos_binance
from services.indicators_service import (
    preparar_tf,
    preparar_1m,
    preparar_5m_contexto,
)
from services.context_service import construir_contexto
from services.liquidity_service import construir_liquidity_engine

from views.sidebar import (
    render_initial_backend_sidebar,
    render_market_sidebar,
)
from views.current_signal_view import render_current_signal_view
from views.backend_monitor_view import render_backend_monitor_tab
from views.context_view import render_context_tab
from views.liquidity_view import render_liquidity_tab
from views.mtf_view import render_mtf_tab
from views.trade_evaluator_view import render_trade_evaluator_tab
from views.backtest_view import render_backtest_tab

from clients.backend_client import get_latest_backend_data


# ============================================================
# STREAMLIT PAGE
# ============================================================

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=PAGE_LAYOUT,
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS — TRADING COCKPIT
# ============================================================

st.markdown(
    """
    <style>
    .main {
        background-color: #0E1117;
    }

    .block-container {
        padding-top: 1.1rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }

    .cockpit-card {
        background: linear-gradient(135deg, #151922 0%, #0f131b 100%);
        border: 1px solid #2a2f3a;
        border-radius: 18px;
        padding: 18px 20px;
        margin-bottom: 14px;
        box-shadow: 0px 8px 24px rgba(0,0,0,0.22);
    }

    .decision-valid {
        background: linear-gradient(135deg, #073b26 0%, #10251c 100%);
        border: 1px solid #1fd17a;
        border-radius: 20px;
        padding: 22px;
        margin-bottom: 16px;
        box-shadow: 0px 8px 26px rgba(31, 209, 122, 0.14);
    }

    .decision-rejected {
        background: linear-gradient(135deg, #401316 0%, #211012 100%);
        border: 1px solid #ff4b4b;
        border-radius: 20px;
        padding: 22px;
        margin-bottom: 16px;
        box-shadow: 0px 8px 26px rgba(255, 75, 75, 0.13);
    }

    .decision-doubt {
        background: linear-gradient(135deg, #40330d 0%, #211d10 100%);
        border: 1px solid #f5c542;
        border-radius: 20px;
        padding: 22px;
        margin-bottom: 16px;
        box-shadow: 0px 8px 26px rgba(245, 197, 66, 0.13);
    }

    .compact-card {
        background: #111722;
        border: 1px solid #252b36;
        border-radius: 16px;
        padding: 14px 16px;
        margin-bottom: 12px;
    }

    .section-title {
        font-size: 1.12rem;
        font-weight: 800;
        margin-bottom: 0.65rem;
        color: #f4f4f4;
    }

    .section-subtitle {
        font-size: 0.86rem;
        color: #9aa4b2;
        margin-top: -0.35rem;
        margin-bottom: 0.85rem;
    }

    .small-label {
        color: #9aa4b2;
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        font-weight: 700;
    }

    .big-status {
        font-size: 2.05rem;
        font-weight: 900;
        line-height: 1.1;
        margin-top: 0.25rem;
    }

    .header-title {
        font-size: 2rem;
        font-weight: 900;
        margin-bottom: 0.1rem;
    }

    .header-caption {
        color: #9aa4b2;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }

    div[data-testid="stMetric"] {
        background: #121722;
        border: 1px solid #252b36;
        padding: 13px 14px;
        border-radius: 14px;
        min-height: 92px;
    }

    div[data-testid="stMetricLabel"] {
        color: #9aa4b2;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.30rem;
        font-weight: 900;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        margin-top: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: #121722;
        border-radius: 12px;
        padding: 10px 16px;
        border: 1px solid #252b36;
        font-weight: 700;
    }

    .stTabs [aria-selected="true"] {
        border: 1px solid #4b86f7 !important;
        background-color: #162033 !important;
    }

    hr {
        margin-top: 0.8rem;
        margin-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS VISUALES
# ============================================================

def fmt_value(value, default="—"):
    if value is None:
        return default
    if value == "":
        return default
    return str(value)


def fmt_price(value, default="—"):
    try:
        if value is None or value == "":
            return default
        return f"{float(value):,.2f}"
    except Exception:
        return str(value)


def fmt_float(value, decimals=2, default="—"):
    try:
        if value is None or value == "":
            return default
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)


def fmt_pct(value, default="—"):
    try:
        if value is None or value == "":
            return default
        return f"{float(value):.1f}%"
    except Exception:
        return str(value)


def normalize_side(side):
    side_str = str(side or "").upper()
    if side_str == "LONG":
        return "🟢 LONG"
    if side_str == "SHORT":
        return "🔴 SHORT"
    return side_str or "—"


def normalize_decision_from_latest(latest_data):
    """
    Solo decisión visual. No cambia lógica backend.
    Usa los campos que ya devuelve get_latest_backend_data().
    """
    if not latest_data or not latest_data.get("ok"):
        return {
            "label": "🟡 SIN ALERTA",
            "css": "decision-doubt",
            "message": "Carga la última alerta o revisa la conexión con backend.",
        }

    approved = latest_data.get("approved")
    validation = latest_data.get("validation")
    quality_score = latest_data.get("quality_score")
    score = latest_data.get("score")

    if approved is True or str(approved).lower() in ["true", "approved", "valid", "ok"]:
        return {
            "label": "🟢 VALID",
            "css": "decision-valid",
            "message": "Última alerta aprobada por backend.",
        }

    if approved is False or str(approved).lower() in ["false", "rejected", "invalid", "no_trade"]:
        return {
            "label": "🔴 NO TRADE",
            "css": "decision-rejected",
            "message": "Última alerta rechazada por backend.",
        }

    if validation:
        validation_str = str(validation).lower()
        if "approved" in validation_str or "valid" in validation_str or "ok" in validation_str:
            return {
                "label": "🟢 VALID",
                "css": "decision-valid",
                "message": "Validación favorable detectada.",
            }

        if "reject" in validation_str or "invalid" in validation_str or "no trade" in validation_str:
            return {
                "label": "🔴 NO TRADE",
                "css": "decision-rejected",
                "message": "Validación desfavorable detectada.",
            }

    numeric_score = None
    for candidate in [score, quality_score]:
        try:
            if candidate is not None and candidate != "":
                numeric_score = float(candidate)
                break
        except Exception:
            pass

    if numeric_score is not None:
        if numeric_score >= 65:
            return {
                "label": "🟢 VALID",
                "css": "decision-valid",
                "message": "Score favorable según última alerta.",
            }
        if numeric_score < 50:
            return {
                "label": "🔴 NO TRADE",
                "css": "decision-rejected",
                "message": "Score débil según última alerta.",
            }

    return {
        "label": "🟡 DUDOSO",
        "css": "decision-doubt",
        "message": "Última alerta cargada, pero sin validación concluyente.",
    }


def render_section_header(title, subtitle=None):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{subtitle}</div>', unsafe_allow_html=True)


# ============================================================
# SIDEBAR — BACKEND
# ============================================================

sidebar_backend_state = render_initial_backend_sidebar()
auto_refresh = sidebar_backend_state["auto_refresh"]
refresh_seconds = sidebar_backend_state["refresh_seconds"]


# ============================================================
# HEADER PRINCIPAL
# ============================================================

header_left, header_right = st.columns([2.2, 1])

with header_left:
    st.markdown(
        '<div class="header-title">📊 Trading Cockpit BTC</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="header-caption">Dashboard operativo para scalping 1m · Backend FastAPI · TradingView Alerts · Binance Market Data</div>',
        unsafe_allow_html=True,
    )

with header_right:
    st.markdown('<div class="compact-card">', unsafe_allow_html=True)
    st.markdown('<div class="small-label">ESTADO DEL PANEL</div>', unsafe_allow_html=True)
    st.write(f"Auto refresh: `{'ON' if auto_refresh else 'OFF'}`")
    st.write(f"Intervalo: `{refresh_seconds}s`")
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# BACKEND ALERT PANEL — ÚLTIMA ALERTA
# ============================================================

if "latest_backend_data" not in st.session_state:
    st.session_state["latest_backend_data"] = {}

st.markdown('<div class="cockpit-card">', unsafe_allow_html=True)
render_section_header(
    "📡 Backend TradingView",
    "Carga manual de la última alerta recibida por el backend. Se mantienen los mismos datos del panel original.",
)

load_col1, load_col2, load_col3 = st.columns([1, 1, 3])

with load_col1:
    cargar_ultima = st.button("🔄 Cargar última alerta", use_container_width=True)

with load_col2:
    limpiar_alerta = st.button("🧹 Limpiar vista", use_container_width=True)

with load_col3:
    st.caption("Este bloque usa `get_latest_backend_data()` exactamente como tu panel anterior.")

if limpiar_alerta:
    st.session_state["latest_backend_data"] = {}

if cargar_ultima:
    latest_data = get_latest_backend_data()
    st.session_state["latest_backend_data"] = latest_data

latest_data = st.session_state.get("latest_backend_data", {})

if latest_data:
    if latest_data.get("ok"):
        st.success("Backend conectado correctamente")
    else:
        st.error("No se pudo cargar la última alerta")
        st.json(latest_data)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# CAPA 1 — DECISIÓN DESDE ÚLTIMA ALERTA
# ============================================================

decision = normalize_decision_from_latest(latest_data)

symbol_backend = latest_data.get("symbol", "-") if latest_data else "-"
side_backend = latest_data.get("side", "-") if latest_data else "-"
setup_backend = latest_data.get("setup", "-") if latest_data else "-"
event_backend = latest_data.get("event", "-") if latest_data else "-"
score_backend = latest_data.get("quality_score", "-") if latest_data else "-"
timeframe_backend = latest_data.get("timeframe", "-") if latest_data else "-"
price_backend = latest_data.get("price", "-") if latest_data else "-"
phase_backend = latest_data.get("phase", "-") if latest_data else "-"
regime_backend = latest_data.get("regime", "-") if latest_data else "-"
phase_5m_backend = latest_data.get("phase_5m", "-") if latest_data else "-"
strength_5m_backend = latest_data.get("strength_5m", "-") if latest_data else "-"
received_at_backend = latest_data.get("received_at", "-") if latest_data else "-"

st.markdown(f'<div class="{decision["css"]}">', unsafe_allow_html=True)

decision_cols = st.columns([1.45, 1, 1, 1, 1])

with decision_cols[0]:
    st.markdown('<div class="small-label">DECISIÓN OPERATIVA</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="big-status">{decision["label"]}</div>', unsafe_allow_html=True)
    st.caption(decision["message"])

with decision_cols[1]:
    st.metric("Side", normalize_side(side_backend))

with decision_cols[2]:
    st.metric("Setup", fmt_value(setup_backend))

with decision_cols[3]:
    st.metric("Score", fmt_value(score_backend))

with decision_cols[4]:
    st.metric("Precio alerta", fmt_price(price_backend))

st.divider()

alert_cols = st.columns(6)

with alert_cols[0]:
    st.metric("Ticker", fmt_value(symbol_backend))

with alert_cols[1]:
    st.metric("Timeframe", fmt_value(timeframe_backend))

with alert_cols[2]:
    st.metric("Evento", fmt_value(event_backend))

with alert_cols[3]:
    st.metric("Phase", fmt_value(phase_backend))

with alert_cols[4]:
    st.metric("Regime", fmt_value(regime_backend))

with alert_cols[5]:
    st.metric("Recibida", fmt_value(received_at_backend))

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# DASHBOARD TITLE
# ============================================================

st.markdown('<div class="cockpit-card">', unsafe_allow_html=True)
render_section_header(
    "📊 Dashboard operativo BTC — Backend Analítico",
    "Market data, contexto MTF, liquidez, evaluación manual de trade y backtest/histórico.",
)
st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# CONFIG GENERAL
# ============================================================

SYMBOL = DEFAULT_SYMBOL


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
    price=contexto["price_1m"],
)


# ============================================================
# SIDEBAR — MARKET
# ============================================================

market_sidebar_state = render_market_sidebar(SYMBOL)
symbol = market_sidebar_state["symbol"]


# ============================================================
# CAPA 1.5 — MARKET SNAPSHOT PRINCIPAL
# ============================================================

st.markdown('<div class="cockpit-card">', unsafe_allow_html=True)
render_section_header(
    "⚡ Market Snapshot",
    "Lectura rápida del estado actual de mercado antes de revisar la señal.",
)

market_cols = st.columns(4)

with market_cols[0]:
    st.metric("Precio 1m", f"{contexto['price_1m']:.2f}")

with market_cols[1]:
    st.metric("FASE 5M", contexto["fase"])

with market_cols[2]:
    st.metric("ADX 5M", f"{contexto['adx_5m']:.2f}")

with market_cols[3]:
    st.metric("Probabilidad base", f"{contexto['probabilidad']:.1f}%")

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# CAPA 2 — SEÑAL ACTUAL
# ============================================================

st.markdown('<div class="cockpit-card">', unsafe_allow_html=True)
render_section_header(
    "🎯 Señal actual",
    "Vista principal de la señal calculada con el contexto actual.",
)

render_current_signal_view(
    contexto=contexto,
    df_5m=df_5m,
)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# TABS — CAPAS DEL DASHBOARD
# ============================================================

tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📡 Monitor Backend",
    "🧭 Contexto",
    "💧 Liquidez",
    "🧪 Validación MTF",
    "🧠 Evaluador de Trade",
    "🕘 Backtest / Histórico",
])


with tab0:
    st.markdown('<div class="cockpit-card">', unsafe_allow_html=True)
    render_section_header(
        "📡 Monitor Backend",
        "Estado del backend, última alerta y datos recuperados desde la capa de integración.",
    )

    render_backend_monitor_tab()

    if latest_data:
        with st.expander("Ver última alerta cargada desde get_latest_backend_data()"):
            st.json(latest_data)

    st.markdown("</div>", unsafe_allow_html=True)


with tab1:
    st.markdown('<div class="cockpit-card">', unsafe_allow_html=True)
    render_section_header(
        "🧭 Contexto de mercado",
        "Filtro principal para decidir si el mercado es operable.",
    )

    render_context_tab(contexto)

    st.markdown("</div>", unsafe_allow_html=True)


with tab2:
    st.markdown('<div class="cockpit-card">', unsafe_allow_html=True)
    render_section_header(
        "💧 Liquidez",
        "Motor de liquidez, sweeps, absorciones y zonas relevantes.",
    )

    render_liquidity_tab(contexto, liquidity)

    st.markdown("</div>", unsafe_allow_html=True)


with tab3:
    st.markdown('<div class="cockpit-card">', unsafe_allow_html=True)
    render_section_header(
        "🧪 Validación MTF",
        "Validación multi-timeframe con 1m, 5m, 15m y 1h.",
    )

    render_mtf_tab(
        df_1m=df_1m,
        df_5m=df_5m,
        df_15m=df_15m,
        df_1h=df_1h,
    )

    st.markdown("</div>", unsafe_allow_html=True)


with tab4:
    st.markdown('<div class="cockpit-card">', unsafe_allow_html=True)
    render_section_header(
        "🧠 Evaluador de Trade",
        "Se conserva el evaluador existente. Aquí debe seguir apareciendo el botón de evaluar trade.",
    )

    render_trade_evaluator_tab(
        contexto=contexto,
        liquidity=liquidity,
        df_5m=df_5m,
    )

    st.markdown("</div>", unsafe_allow_html=True)


with tab5:
    st.markdown('<div class="cockpit-card">', unsafe_allow_html=True)
    render_section_header(
        "🕘 Backtest / Histórico",
        "Histórico operativo y análisis de resultados.",
    )

    render_backtest_tab(df_1m)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# AUTO REFRESH
# ============================================================

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()