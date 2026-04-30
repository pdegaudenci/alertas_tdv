"""
Helpers visuales reutilizables para Streamlit.

Este archivo contiene componentes pequeños usados por varias secciones del panel.
No calcula indicadores ni reglas de trading.

"""

import streamlit as st


def render_info_item(titulo: str, explicacion: str, estado: str = "info") -> None:
    """
    Muestra una línea con icono + texto y debajo un desplegable pequeño con explicación.

    estado:
    - info
    - success
    - warning
    - error
    """

    if estado == "success":
        st.success(titulo)
    elif estado == "warning":
        st.warning(titulo)
    elif estado == "error":
        st.error(titulo)
    else:
        st.info(titulo)

    with st.expander(f"ℹ️ Ver explicación: {titulo}", expanded=False):
        st.write(explicacion)


def render_json_expander(title: str, data, expanded: bool = False) -> None:
    """
    Renderiza un expander con JSON.

    Se usará en próximas fases para payloads, validaciones y snapshots.
    """

    with st.expander(title, expanded=expanded):
        st.json(data)


def render_text_list(items, empty_message: str = "Sin datos registrados", success: bool = True) -> None:
    """
    Renderiza una lista de textos con st.success o st.error.

    Se usará después para razones y penalizaciones.
    """

    if not items:
        st.info(empty_message)
        return

    for item in items:
        if success:
            st.success(f"✔ {item}")
        else:
            st.error(f"✖ {item}")


def render_section_divider() -> None:
    """
    Renderiza separador visual estándar.
    """

    st.markdown("---")