"""
Backend Monitor View del panel Streamlit.

Este archivo contiene el tab "Monitor Backend" del dashboard.

Responsabilidad:
- Mostrar última alerta recibida desde backend.
- Mostrar última validación.
- Mostrar histórico Supabase.
- Mostrar payloads normalizados, técnicos y crudos.
- Mantener el comportamiento visual original del tab0.


"""

from typing import Any, Dict

import pandas as pd
import streamlit as st

from clients.backend_client import (
    get_latest_backend_data,
    get_latest_validation_data,
    get_alerts_history_supabase,
)

from services.alert_view_service import (
    unwrap_latest_response,
    extract_latest_alert_summary,
    build_latest_alert_metrics,
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


def render_backend_monitor_tab() -> None:
    """
    Renderiza el tab completo "Monitor Backend".

    Este contenido viene del bloque original:

    with tab0:
        st.subheader("📡 Monitor de alertas procesadas por Vercel")
        ...
    """

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
            index=2,
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
            latest_metrics = build_latest_alert_metrics(latest_data)

            validation = latest_summary.get("validation", {}) or {}
            validation_block = extract_validation_block(latest_data)
            payload_block = latest_summary.get("payload", {}) or {}

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Símbolo", latest_data.get("symbol", "-"))
            c2.metric("Side", str(latest_data.get("side", "-")).upper())
            c3.metric("Evento", latest_data.get("event", "-"))
            c4.metric("TF", latest_data.get("timeframe", "-"))

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Precio", latest_data.get("price", "-"))
            c6.metric("Phase", latest_data.get("phase", "-"))
            c7.metric("Regime", latest_data.get("regime", "-"))
            c8.metric("Quality", latest_data.get("quality_score", "-"))

            st.write("Setup:", latest_data.get("setup", "-"))
            st.write("Phase 5m:", latest_data.get("phase_5m", "-"))
            st.write("Strength 5m:", latest_data.get("strength_5m", "-"))
            st.write("Recibida:", latest_data.get("received_at", "-"))

            st.markdown("---")
            st.markdown("## Resultado de validación")

            validation_metrics = build_validation_metrics(validation_block)

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

            validation_sections = extract_validation_sections(validation_block)
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

            market_snapshot = validation_block.get("market_snapshot", {}) or {}
            if market_snapshot:
                st.markdown("### Snapshot de mercado usado por backend")
                snap_df = pd.DataFrame([market_snapshot])
                st.dataframe(snap_df, use_container_width=True)

            structure_snapshot = validation_block.get("structure_snapshot", {}) or {}
            if structure_snapshot:
                st.markdown("### Snapshot estructural")
                st.json(structure_snapshot)

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

    except Exception as e:
        st.error(f"Error conectando con backend: {e}")