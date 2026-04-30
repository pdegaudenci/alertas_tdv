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


# ============================================================
# STREAMLIT PAGE
# ============================================================

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=PAGE_LAYOUT,
)


# ============================================================
# BACKEND ALERT PANEL
# ============================================================

st.title("Panel de alertas TradingView")

sidebar_backend_state = render_initial_backend_sidebar()
auto_refresh = sidebar_backend_state["auto_refresh"]
refresh_seconds = sidebar_backend_state["refresh_seconds"]

## ULYIMA ALERTA
from clients.backend_client import get_latest_backend_data
if st.button("Cargar última alerta"):
    latest_data = get_latest_backend_data()

    if latest_data.get("ok"):
        st.success("Backend conectado correctamente")

        st.subheader("Última señal")
        st.write("Ticker:", latest_data.get("symbol", "-"))
        st.write("Side:", latest_data.get("side", "-"))
        st.write("Setup:", latest_data.get("setup", "-"))
        st.write("Evento:", latest_data.get("event", "-"))
        st.write("Score:", latest_data.get("quality_score", "-"))
        st.write("Timeframe:", latest_data.get("timeframe", "-"))
        st.write("Precio:", latest_data.get("price", "-"))
        st.write("Phase:", latest_data.get("phase", "-"))
        st.write("Regime:", latest_data.get("regime", "-"))
        st.write("Phase 5m:", latest_data.get("phase_5m", "-"))
        st.write("Strength 5m:", latest_data.get("strength_5m", "-"))
        st.write("Recibida:", latest_data.get("received_at", "-"))
    else:
        st.error("No se pudo cargar la última alerta")
        st.json(latest_data)
# ============================================================
# DASHBOARD TITLE
# ============================================================

st.title("📊 DASHBOARD OPERATIVO BTC - BACKEND ANALÍTICO")


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

render_current_signal_view(
    contexto=contexto,
    df_5m=df_5m,
)


# ============================================================
# TABS
# ============================================================

tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Monitor Backend",
    "Contexto",
    "Liquidez",
    "Validación MTF",
    "Evaluador de Trade",
    "Backtest / Histórico",
])


with tab0:
    render_backend_monitor_tab()

with tab1:
    render_context_tab(contexto)

with tab2:
    render_liquidity_tab(contexto, liquidity)

with tab3:
    render_mtf_tab(
        df_1m=df_1m,
        df_5m=df_5m,
        df_15m=df_15m,
        df_1h=df_1h,
    )

with tab4:
    render_trade_evaluator_tab(
        contexto=contexto,
        liquidity=liquidity,
        df_5m=df_5m,
    )

with tab5:
    render_backtest_tab(df_1m)


# ============================================================
# AUTO REFRESH
# ============================================================

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()