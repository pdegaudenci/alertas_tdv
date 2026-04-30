"""
Liquidity View del panel Streamlit.

Este archivo contiene el tab "Liquidez" del dashboard.

Responsabilidad:
- Mostrar liquidez cercana.
- Mostrar distancia a resistencia/soporte en ATR.
- Mostrar intención probable del mercado.
- Mostrar zonas institucionales.
- Mostrar riesgo de liquidez.
- Mostrar estado operativo del mercado.


"""

from typing import Dict, Any

import streamlit as st


def render_liquidity_tab(
    contexto: Dict[str, Any],
    liquidity: Dict[str, Any],
) -> None:
    """
    Renderiza el tab Liquidez.

    Equivale al bloque original:

    with tab2:
        ...
    """

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