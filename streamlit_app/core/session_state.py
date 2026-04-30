"""
Gestión de session_state del panel Streamlit.

Este archivo centraliza claves y valores iniciales para evitar que el estado
quede disperso en múltiples vistas.


"""

from typing import Any

import streamlit as st


# ============================================================
# SESSION KEYS
# ============================================================

KEY_AUTO_REFRESH = "auto_refresh"
KEY_REFRESH_SECONDS = "refresh_seconds"
KEY_SELECTED_HISTORY_LIMIT = "selected_history_limit"
KEY_LAST_MANUAL_REFRESH = "last_manual_refresh"
KEY_SELECTED_ALERT_INDEX = "selected_alert_index"
KEY_SELECTED_SETUP_ID = "selected_setup_id"


# ============================================================
# INITIALIZATION
# ============================================================

def init_session_state() -> None:
    """
    Inicializa las claves mínimas usadas por el panel.

    Debe llamarse una sola vez al principio de app.py.
    """

    defaults = {
        KEY_AUTO_REFRESH: True,
        KEY_REFRESH_SECONDS: 10,
        KEY_SELECTED_HISTORY_LIMIT: 50,
        KEY_LAST_MANUAL_REFRESH: None,
        KEY_SELECTED_ALERT_INDEX: None,
        KEY_SELECTED_SETUP_ID: None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_state(key: str, default: Any = None) -> Any:
    """
    Lee un valor desde st.session_state.
    """

    return st.session_state.get(key, default)


def set_state(key: str, value: Any) -> None:
    """
    Escribe un valor en st.session_state.
    """

    st.session_state[key] = value


def clear_dashboard_cache() -> None:
    """
    Limpia cache de Streamlit y fuerza recarga posterior.
    """

    st.cache_data.clear()