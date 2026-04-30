"""
Sidebar View del panel Streamlit.

Este archivo contiene la visualización del sidebar principal.

Responsabilidad:
- Configuración visual del dashboard.
- Auto refresh.
- Botón de actualización.
- Mostrar fuentes de datos.
- Mantener el comportamiento original del panel.


"""

from typing import Dict, Any

import streamlit as st

from core.config import BINANCE_BASE_URLS
from core.constants import (
    DEFAULT_AUTO_REFRESH,
    DEFAULT_REFRESH_SECONDS,
    MIN_REFRESH_SECONDS,
    MAX_REFRESH_SECONDS,
)


def render_initial_backend_sidebar() -> Dict[str, Any]:
    """
    Renderiza el sidebar inicial del bloque de alertas backend.

    Corresponde al primer bloque original:

    auto_refresh = st.sidebar.checkbox(...)
    refresh_seconds = st.sidebar.slider(...)
    """

    auto_refresh = st.sidebar.checkbox(
        "Auto refresh backend",
        value=DEFAULT_AUTO_REFRESH,
    )

    refresh_seconds = st.sidebar.slider(
        "Refresh backend cada segundos",
        MIN_REFRESH_SECONDS,
        MAX_REFRESH_SECONDS,
        DEFAULT_REFRESH_SECONDS,
    )

    if auto_refresh:
        st.sidebar.info(f"Auto refresh activo cada {refresh_seconds}s")

    return {
        "auto_refresh": auto_refresh,
        "refresh_seconds": refresh_seconds,
    }


def render_market_sidebar(symbol: str) -> Dict[str, Any]:
    """
    Renderiza el sidebar de configuración de mercado.

    Corresponde al bloque original:

    st.sidebar.header("Configuración")
    symbol = st.sidebar.text_input(...)
    st.sidebar.write(...)
    botón actualizar
    fuentes de datos
    """

    st.sidebar.header("Configuración")

    selected_symbol = st.sidebar.text_input(
        "Símbolo",
        value=symbol,
        disabled=True,
    )

    st.sidebar.write("Actualización automática cada 60s por cache.")

    refresh_clicked = st.sidebar.button("Actualizar mercado ahora")

    if refresh_clicked:
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Fuente de datos")
    st.sidebar.write("Endpoints probados en orden:")

    for endpoint in BINANCE_BASE_URLS:
        st.sidebar.code(endpoint, language=None)

    return {
        "symbol": selected_symbol,
        "refresh_clicked": refresh_clicked,
    }