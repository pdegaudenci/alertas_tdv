"""
Componentes de tablas para el panel Streamlit.

Estos helpers centralizan st.dataframe y preparación visual básica.
"""

from typing import Any

import pandas as pd
import streamlit as st


def render_dataframe(
    df: pd.DataFrame,
    empty_message: str = "No hay datos disponibles",
    use_container_width: bool = True
) -> None:
    """
    Renderiza DataFrame si tiene datos.
    """

    if df is None or df.empty:
        st.info(empty_message)
        return

    st.dataframe(df, use_container_width=use_container_width)


def render_dict_as_dataframe(
    data: dict[str, Any],
    empty_message: str = "No hay datos disponibles"
) -> None:
    """
    Renderiza un diccionario como DataFrame de una fila.
    """

    if not isinstance(data, dict) or not data:
        st.info(empty_message)
        return

    st.dataframe(pd.DataFrame([data]), use_container_width=True)