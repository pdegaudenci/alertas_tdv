"""
Trade Evaluator View del panel Streamlit.

Este archivo contiene el tab "Evaluador de Trade" del dashboard.

Responsabilidad:
- Renderizar el formulario de evaluación manual.
- Calcular score de mercado visual.
- Calcular calidad de entrada.
- Mostrar gestión de trade.
- Mostrar probabilidad TP, rentabilidad, calidad técnica y decisión final.
- Mostrar análisis de liquidez del trade.
- Mostrar gestión de posición.


"""

from typing import Dict, Any

import streamlit as st

from utils.math_utils import rating_score
from components.ui_helpers import render_info_item

from services.trade_engine_service import (
    compute_trade_levels,
    calcular_posicion_real,
)

from services.probability_service import (
    probabilidad_tp_real,
    probabilidad_rentable,
)

from services.liquidity_service import liquidity_risk_explained

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


def render_trade_evaluator_tab(
    contexto: Dict[str, Any],
    liquidity: Dict[str, Any],
    df_5m,
) -> None:
    """
    Renderiza el tab Evaluador Integral de Trade.

    Equivale al bloque original:

    with tab4:
        ...
    """

    st.title("🧠 Evaluador Integral de Trade")
    st.write("Mínimo recomendado para operar: 65%")

    with st.form("trade_eval"):
        entrada = st.number_input(
            "Precio de entrada",
            value=float(contexto["price_1m"]),
            step=0.1,
        )
        direccion = st.selectbox("Dirección", ["LONG", "SHORT"])
        evaluar = st.form_submit_button("Evaluar Trade")

    if evaluar:
        st.markdown("---")
        st.header("Análisis del Trade")

        # ========================================================
        # 1) CONDICIÓN DEL MERCADO
        # ========================================================
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

        # --------------------------------------------------------
        # Leyendas explicativas de los factores activos
        # --------------------------------------------------------
        if contexto["adx_5m"] > 25:
            render_info_item(
                "• Mercado con fuerza (ADX > 25)",
                explicacion_mercado_fuerza(),
                estado="success",
            )

        elif contexto["adx_5m"] > 22:
            render_info_item(
                "• Impulso moderado (ADX > 22)",
                """
**Impulso moderado**

El ADX está por encima del umbral mínimo de debilidad, pero aún no habla de una tendencia muy potente.
Esto sugiere que el mercado puede moverse, aunque con menos autoridad que en un escenario de ADX > 25.
""".strip(),
                estado="info",
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
                estado="warning",
            )

        if contexto["fase"] == "RANGO":
            render_info_item(
                f"• Fase {contexto['fase']}",
                explicacion_fase(contexto["fase"]),
                estado="warning",
            )
        else:
            render_info_item(
                f"• Fase {contexto['fase']}",
                explicacion_fase(contexto["fase"]),
                estado="success",
            )

        if contexto["vela_extendida"]:
            render_info_item(
                "• Vela 1m extendida (posible clímax)",
                explicacion_climax(),
                estado="warning",
            )

        if contexto["adx_cayendo"]:
            render_info_item(
                "• ADX cayendo (pérdida de fuerza)",
                explicacion_adx_cayendo(),
                estado="warning",
            )

        if not contexto["vela_extendida"] and not contexto["adx_cayendo"]:
            st.success("• No hay señales claras de agotamiento en este momento")

        # ========================================================
        # 2) VALIDACIÓN DE ENTRADA
        # ========================================================
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

            texto = f"{nombre} | Valor: {valor} | Impacto: {impacto}"

            if positivo:
                st.success(f"✔ {texto}")
            else:
                st.error(f"✖ {texto}")

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

        # ========================================================
        # 3) GESTIÓN DEL TRADE
        # ========================================================
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
            strong_supports=liquidity["strong_supports"],
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
            above_vwap=contexto["above_vwap"],
        )

        prob_profit = probabilidad_rentable(prob_tp, niveles["rr"])

        st.write(f"Riesgo real: {niveles['risk_pct']:.3f}% ({niveles['risk_label']})")
        st.write(f"Beneficio potencial: {niveles['reward_pct']:.3f}% ({niveles['reward_label']})")
        st.write(f"R:R real: {niveles['rr']:.2f} ({niveles['rr_label']})")

        # ========================================================
        # PROBABILIDAD TP
        # ========================================================
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
                    liquidity_attraction=liquidity["liquidity_attraction"],
                )
            )

        # ========================================================
        # PROBABILIDAD RENTABLE
        # ========================================================
        st.subheader("Probabilidad de rentabilidad")
        st.progress(prob_profit / 100)
        st.write(f"{prob_profit:.1f}%")

        with st.expander("ℹ️ Cómo se calculó la probabilidad de rentabilidad", expanded=False):
            st.write(
                explicacion_prob_rentable(
                    prob_profit=prob_profit,
                    prob_tp=prob_tp,
                    rr=niveles["rr"],
                )
            )

        # ========================================================
        # CALIDAD TÉCNICA DEL SETUP
        # ========================================================
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
                    lrs_score=lrs_info["score"],
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

        # ========================================================
        # LIQUIDITY RISK ANALYSIS
        # ========================================================
        st.subheader("Liquidity Risk Analysis")
        st.metric(
            "Trade Liquidity Risk",
            f"{lrs_info['score']}/80 ({lrs_info['label']})",
        )

        for item in lrs_info["debug"]:
            st.write("•", item)

        # ========================================================
        # GESTIÓN DE POSICIÓN
        # ========================================================
        st.subheader("Gestión de la Posición")

        datos_posicion = calcular_posicion_real(
            entrada,
            niveles["sl"],
            niveles["tp"],
        )

        if datos_posicion:
            p1, p2, p3 = st.columns(3)

            p1.metric("Tamaño posición", f"{datos_posicion['posicion']:.0f} €")
            p2.metric("Margen necesario", f"{datos_posicion['margen']:.2f} €")
            p3.metric("Riesgo real", f"{datos_posicion['riesgo']:.2f} €")

            st.write(f"Ganancia neta estimada: **{datos_posicion['beneficio']:.2f} €**")
            st.write(f"Comisiones aproximadas: {datos_posicion['comisiones']:.2f} €")
            st.write(f"Pérdida máxima: **-{datos_posicion['riesgo']:.2f} €**")

            rr_real = (
                datos_posicion["beneficio"] / datos_posicion["riesgo"]
                if datos_posicion["riesgo"] > 0
                else 0
            )

            if rr_real >= 1.4:
                st.success("El trade es matemáticamente rentable")
            elif rr_real >= 1.1:
                st.warning("Trade aceptable pero justo")
            else:
                st.error("Trade NO rentable → NO operar")
        else:
            st.error("No se puede calcular el tamaño de posición")