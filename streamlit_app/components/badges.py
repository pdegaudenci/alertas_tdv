"""
Badges visuales simples para estados del panel.

No reemplaza todavía bloques existentes del app.py.
Queda preparado para la siguiente fase de vistas.
"""

import streamlit as st


def render_approve_badge(approve) -> None:
    """
    Renderiza estado approve.
    """

    if approve is True:
        st.success("✅ Señal aprobada por Validation Layer")
    elif approve is False:
        st.error("⛔ Señal rechazada por Validation Layer")
    else:
        st.warning("⚠ Validación no disponible")


def render_boolean_badge(label: str, value) -> None:
    """
    Renderiza booleanos con estado visual.
    """

    if value is True:
        st.success(f"{label}: TRUE")
    elif value is False:
        st.error(f"{label}: FALSE")
    else:
        st.info(f"{label}: -")


def render_direction_badge(side: str) -> None:
    """
    Renderiza dirección LONG / SHORT.
    """

    side_upper = str(side or "-").upper()

    if side_upper == "LONG":
        st.success("LONG")
    elif side_upper == "SHORT":
        st.error("SHORT")
    else:
        st.info(side_upper)