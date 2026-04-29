"""
Cliente HTTP para consumir el backend FastAPI / Validation Layer.

Responsabilidad:
- Centralizar llamadas requests.get()
- Manejar timeouts
- Manejar errores HTTP
- Devolver diccionarios seguros para que la UI no falle
- Mantener cache de Streamlit donde ya existía en el panel original

Este archivo NO debe renderizar componentes Streamlit.
Solo obtiene datos desde el backend.
"""

from typing import Dict, Any

import requests
import streamlit as st

from core.config import (
    BACKEND_BASE_URL,
    BACKEND_LATEST_URL,
    BACKEND_ALERTS_URL,
    BACKEND_VALIDATION_URL,
    BACKEND_ALERTS_SUPABASE_URL,
    BACKEND_SETUPS_SUPABASE_URL,
    BACKEND_HEALTH_URL,
    BACKEND_BINANCE_HEALTH_URL,
    BACKEND_SUPABASE_HEALTH_URL,
    DEFAULT_REQUEST_TIMEOUT,
    SHORT_REQUEST_TIMEOUT,
    CACHE_TTL_SECONDS,
)


def fetch_backend_json(url: str, timeout: int = DEFAULT_REQUEST_TIMEOUT) -> Dict[str, Any]:
    """
    Ejecuta un GET contra el backend y devuelve JSON.

    Mantiene comportamiento seguro:
    - Si hay timeout, devuelve ok=False con items=[]
    - Si hay error HTTP o de conexión, devuelve ok=False con items=[]
    - No lanza excepción hacia la UI
    """

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict):
            return data

        return {
            "ok": True,
            "data": data,
            "items": data if isinstance(data, list) else [],
        }

    except requests.exceptions.ReadTimeout:
        return {
            "ok": False,
            "error": "TIMEOUT",
            "message": f"El backend no respondió en {timeout} segundos",
            "items": [],
        }

    except requests.exceptions.ConnectionError as e:
        return {
            "ok": False,
            "error": "CONNECTION_ERROR",
            "message": str(e),
            "items": [],
        }

    except requests.exceptions.HTTPError as e:
        status_code = None
        text = None

        try:
            status_code = e.response.status_code
            text = e.response.text
        except Exception:
            pass

        return {
            "ok": False,
            "error": "HTTP_ERROR",
            "status_code": status_code,
            "message": str(e),
            "response_text": text,
            "items": [],
        }

    except Exception as e:
        return {
            "ok": False,
            "error": "BACKEND_ERROR",
            "message": str(e),
            "items": [],
        }


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_latest_backend_data() -> Dict[str, Any]:
    """
    Devuelve la última alerta recibida por el backend.

    Endpoint:
    GET /api/latest
    """

    return fetch_backend_json(BACKEND_LATEST_URL, timeout=SHORT_REQUEST_TIMEOUT)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_latest_validation_data() -> Dict[str, Any]:
    """
    Devuelve la última validación generada por el backend.

    Endpoint:
    GET /api/validation/latest
    """

    return fetch_backend_json(BACKEND_VALIDATION_URL, timeout=SHORT_REQUEST_TIMEOUT)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_alerts_history(limit: int = 50) -> Dict[str, Any]:
    """
    Devuelve histórico en memoria del backend.

    Endpoint:
    GET /api/alerts?limit=N
    """

    return fetch_backend_json(
        f"{BACKEND_ALERTS_URL}?limit={limit}",
        timeout=DEFAULT_REQUEST_TIMEOUT,
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_alerts_history_supabase(limit: int = 50) -> Dict[str, Any]:
    """
    Devuelve histórico persistido en Supabase a través del backend.

    Endpoint:
    GET /api/alerts/supabase?limit=N
    """

    return fetch_backend_json(
        f"{BACKEND_ALERTS_SUPABASE_URL}?limit={limit}",
        timeout=DEFAULT_REQUEST_TIMEOUT,
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_setups_supabase(limit: int = 50) -> Dict[str, Any]:
    """
    Devuelve setups persistidos en Supabase a través del backend.

    Endpoint:
    GET /api/setups/supabase?limit=N
    """

    return fetch_backend_json(
        f"{BACKEND_SETUPS_SUPABASE_URL}?limit={limit}",
        timeout=DEFAULT_REQUEST_TIMEOUT,
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def health_backend() -> Dict[str, Any]:
    """
    Healthcheck general del backend.

    Endpoint:
    GET /
    """

    return fetch_backend_json(BACKEND_HEALTH_URL, timeout=SHORT_REQUEST_TIMEOUT)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def health_binance() -> Dict[str, Any]:
    """
    Healthcheck de Binance desde el backend.

    Endpoint:
    GET /api/health/binance
    """

    return fetch_backend_json(BACKEND_BINANCE_HEALTH_URL, timeout=DEFAULT_REQUEST_TIMEOUT)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def health_supabase() -> Dict[str, Any]:
    """
    Healthcheck de Supabase desde el backend.

    Endpoint:
    GET /api/health/supabase
    """

    return fetch_backend_json(BACKEND_SUPABASE_HEALTH_URL, timeout=DEFAULT_REQUEST_TIMEOUT)


def get_backend_base_url() -> str:
    """
    Devuelve la URL base configurada para el backend.
    """

    return BACKEND_BASE_URL