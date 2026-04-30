"""
Configuración centralizada del panel Streamlit.

Este archivo concentra URLs del backend, parámetros generales del dashboard
y configuración cargada desde variables de entorno.

Objetivo:
- Evitar URLs hardcodeadas repartidas por el panel.
- Facilitar despliegue local / producción.
- Mantener una única fuente de verdad para endpoints.
"""

import os
from dotenv import load_dotenv

# Carga variables desde .env en entorno local.
# En Streamlit Cloud / Vercel / Docker también funcionará con variables del entorno.
load_dotenv()


# ============================================================
# HELPERS ENV
# ============================================================

def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


# ============================================================
# BACKEND API
# ============================================================

BACKEND_BASE_URL = env_str(
    "BACKEND_BASE_URL",
    "http://localhost:8000"
).rstrip("/")

BACKEND_LATEST_URL = f"{BACKEND_BASE_URL}/api/latest"
BACKEND_ALERTS_URL = f"{BACKEND_BASE_URL}/api/alerts"
BACKEND_VALIDATION_URL = f"{BACKEND_BASE_URL}/api/validation/latest"
BACKEND_ALERTS_SUPABASE_URL = f"{BACKEND_BASE_URL}/api/alerts/supabase"
BACKEND_SETUPS_SUPABASE_URL = f"{BACKEND_BASE_URL}/api/setups/supabase"

BACKEND_HEALTH_URL = f"{BACKEND_BASE_URL}/"
BACKEND_BINANCE_HEALTH_URL = f"{BACKEND_BASE_URL}/api/health/binance"
BACKEND_SUPABASE_HEALTH_URL = f"{BACKEND_BASE_URL}/api/health/supabase"


# ============================================================
# REQUESTS
# ============================================================

DEFAULT_REQUEST_TIMEOUT = env_int("STREAMLIT_REQUEST_TIMEOUT", 25)
SHORT_REQUEST_TIMEOUT = env_int("STREAMLIT_SHORT_REQUEST_TIMEOUT", 10)


# ============================================================
# STREAMLIT CACHE
# ============================================================

CACHE_TTL_SECONDS = env_int("STREAMLIT_CACHE_TTL_SECONDS", 5)


# ============================================================
# PAGE CONFIG
# ============================================================

PAGE_TITLE = env_str("STREAMLIT_PAGE_TITLE", "Panel Operativo BTC")
PAGE_ICON = env_str("STREAMLIT_PAGE_ICON", "📊")
PAGE_LAYOUT = env_str("STREAMLIT_PAGE_LAYOUT", "wide")


# ============================================================
# SYMBOL
# ============================================================

DEFAULT_SYMBOL = env_str("TRADING_SYMBOL", "BTCUSDC").upper()


# ============================================================
# BINANCE
# ============================================================

BINANCE_BASE_URLS = [
    url.strip().rstrip("/")
    for url in env_str(
        "BINANCE_BASE_URLS",
        "https://data-api.binance.vision,https://data.binance.com,https://api.binance.us"
    ).split(",")
    if url.strip()
]


# ============================================================
# LOGGING / LOCAL FILES
# ============================================================

LOG_FILE = env_str("STREAMLIT_SIGNAL_LOG_FILE", "signals_log.csv")


# ============================================================
# UI DEFAULTS
# ============================================================

DEFAULT_AUTO_REFRESH = env_bool("STREAMLIT_DEFAULT_AUTO_REFRESH", True)
DEFAULT_REFRESH_SECONDS = env_int("STREAMLIT_DEFAULT_REFRESH_SECONDS", 10)
MIN_REFRESH_SECONDS = env_int("STREAMLIT_MIN_REFRESH_SECONDS", 5)
MAX_REFRESH_SECONDS = env_int("STREAMLIT_MAX_REFRESH_SECONDS", 60)

DEFAULT_HISTORY_LIMIT = env_int("STREAMLIT_DEFAULT_HISTORY_LIMIT", 50)
HISTORY_LIMIT_OPTIONS = [10, 20, 50, 100]


# ============================================================
# DEBUG
# ============================================================

STREAMLIT_DEBUG = env_bool("STREAMLIT_DEBUG", False)