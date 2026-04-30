"""
Context View del panel Streamlit.

Este archivo contiene el tab "Contexto" del dashboard.

Responsabilidad:
- Mostrar régimen de mercado.
- Mostrar RSI, ROC, ATR.
- Mostrar contexto VWAP / EMA200 / EMAs.
- Mostrar compresión de volatilidad.
- Mostrar EV base.


"""

from typing import Dict, Any

import streamlit as st


def render_context_tab(contexto: Dict[str, Any]) -> None:
    """
    Renderiza el tab Contexto.

    Equivale al bloque original:

    with tab1:
        ...
    """

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
    st.write(
        "Stack EMAs 1m:",
        "Alcista" if contexto["ema_bullish_stack"] else "Bajista" if contexto["ema_bearish_stack"] else "Mixto",
    )
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