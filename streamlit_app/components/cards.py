"""
Componentes de cards y métricas para el panel Streamlit.

En esta fase se agregan helpers simples para futuras migraciones de vistas.
No es obligatorio usarlos todavía en app.py.
"""

from typing import Any, Optional

import streamlit as st


def render_metric_card(
    title: str,
    value: Any,
    help_text: Optional[str] = None
) -> None:
    """
    Renderiza una métrica individual.
    """

    st.metric(label=title, value=value, help=help_text)


def render_four_metrics(
    labels_and_values: list[tuple[str, Any]]
) -> None:
    """
    Renderiza hasta 4 métricas en una fila.

    Ejemplo:
    render_four_metrics([
        ("Símbolo", "BTCUSDC"),
        ("Side", "LONG"),
        ("Evento", "LONG_ENTRY"),
        ("TF", "1m"),
    ])
    """

    cols = st.columns(4)

    for col, item in zip(cols, labels_and_values[:4]):
        label, value = item
        col.metric(label, value)


def render_status_message(
    status: str,
    message: str
) -> None:
    """
    Renderiza mensaje según estado.

    status:
    - success
    - warning
    - error
    - info
    """

    if status == "success":
        st.success(message)
    elif status == "warning":
        st.warning(message)
    elif status == "error":
        st.error(message)
    else:
        st.info(message)