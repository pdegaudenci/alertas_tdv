"""
Configuración central del backend.

Este archivo concentra las variables de entorno y constantes globales
para que el resto de módulos pueda importarla.
"""

import os
import json
from typing import List

BINANCE_BASE_URLS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
]

WEBHOOK_SECRET_ENV = os.getenv("WEBHOOK_SECRET", "")

VALIDATION_THRESHOLD = float(os.getenv("VALIDATION_THRESHOLD", "0.62"))
MIN_SCORE_THRESHOLD = float(os.getenv("MIN_SCORE_THRESHOLD", "55"))
REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "8.0"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = ["*"]

SKLEARN_MODEL = None
SKLEARN_FEATURE_ORDER: List[str] = []

try:
    import joblib  # type: ignore

    model_path = os.getenv("ML_MODEL_PATH", "").strip()
    feat_path = os.getenv("ML_FEATURES_JSON", "").strip()

    if model_path and os.path.exists(model_path):
        SKLEARN_MODEL = joblib.load(model_path)

    if feat_path and os.path.exists(feat_path):
        with open(feat_path, "r", encoding="utf-8") as fh:
            SKLEARN_FEATURE_ORDER = json.load(fh)

except Exception:
    SKLEARN_MODEL = None
    SKLEARN_FEATURE_ORDER = []

# ============================================================
# DATABRICKS / LAKEHOUSE EXPORT
# ============================================================

ENABLE_DATABRICKS_EXPORT = os.getenv("ENABLE_DATABRICKS_EXPORT", "false").lower() == "true"

DATABRICKS_EXPORT_TARGET = os.getenv(
    "DATABRICKS_EXPORT_TARGET",
    "local"
).strip().lower()

DATABRICKS_EXPORT_BASE_PATH = os.getenv(
    "DATABRICKS_EXPORT_BASE_PATH",
    "/tmp/trading_lakehouse"
)

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "").strip()

GCS_BASE_PREFIX = os.getenv(
    "GCS_BASE_PREFIX",
    "bronze/trading_alerts"
).strip().strip("/")

GCP_SERVICE_ACCOUNT_JSON_BASE64 = os.getenv(
    "GCP_SERVICE_ACCOUNT_JSON_BASE64",
    ""
).strip()