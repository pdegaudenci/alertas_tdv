"""
Current Signal View del panel Streamlit.

Este archivo contiene el bloque visual "Señal Actual del Entorno".

Responsabilidad:
- Calcular niveles LONG y SHORT para el entorno actual.
- Mostrar si el contexto actual permite LONG, SHORT, espera o ambigüedad.
- Registrar la señal con log_signal() cuando el entorno es válido.


"""

from typing import Dict, Any

import pandas as pd
import streamlit as st

from services.trade_engine_service import compute_trade_levels
from services.backtest_service import log_signal


def render_current_signal_view(
    contexto: Dict[str, Any],
    df_5m: pd.DataFrame,
) -> None:
    """
    Renderiza el bloque "Señal Actual del Entorno".

    Equivale al bloque original:

    st.subheader("Señal Actual del Entorno")

    trade_levels_long = compute_trade_levels(...)
    trade_levels_short = compute_trade_levels(...)

    if contexto["long_valido"] ...
    """

    st.subheader("Señal Actual del Entorno")

    trade_levels_long = compute_trade_levels(
        entrada=contexto["price_1m"],
        direccion="LONG",
        df_5m=df_5m,
        adx_5m=contexto["adx_5m"],
    )

    trade_levels_short = compute_trade_levels(
        entrada=contexto["price_1m"],
        direccion="SHORT",
        df_5m=df_5m,
        adx_5m=contexto["adx_5m"],
    )

    if contexto["long_valido"] and not contexto["short_valido"]:
        st.success("🚀 LONG VÁLIDO")
        st.write("TP:", round(trade_levels_long["tp"], 2))
        st.write("SL:", round(trade_levels_long["sl"], 2))

        log_signal(
            "LONG",
            contexto["probabilidad"],
            contexto["fase"],
            contexto["adx_5m"],
            contexto["rsi_1m"],
        )

    elif contexto["short_valido"] and not contexto["long_valido"]:
        st.error("🔻 SHORT VÁLIDO")
        st.write("TP:", round(trade_levels_short["tp"], 2))
        st.write("SL:", round(trade_levels_short["sl"], 2))

        log_signal(
            "SHORT",
            contexto["probabilidad"],
            contexto["fase"],
            contexto["adx_5m"],
            contexto["rsi_1m"],
        )

    elif contexto["long_valido"] and contexto["short_valido"]:
        st.warning("⚠ Contexto ambiguo. Esperar confirmación externa del trigger.")

    else:
        st.warning("⏳ ESPERAR")