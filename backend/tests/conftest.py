"""
Configuración común para tests con pytest.

Incluye fixtures para:
- FastAPI TestClient
- Mocks de servicios externos: AWS S3, SQS, Supabase, Binance, etc.
- Configuración de entorno de test
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# ENV VARS DE TEST ANTES DE IMPORTAR LA APP
# =============================================================================
# Importante:
# app.main puede importar config/settings en tiempo de importación.
# Por eso dejamos valores seguros de test antes de importar la app FastAPI.

os.environ.setdefault("WEBHOOK_SECRET", "test_secret")
os.environ.setdefault(
    "SQS_QUEUE_URL",
    "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
)
os.environ.setdefault("DATABRICKS_EXPORT_TARGET", "local")
os.environ.setdefault("ENABLE_DATABRICKS_EXPORT", "true")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("APP_ENV", "test")

# Variables opcionales para evitar errores si algún módulo las espera.
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test_supabase_service_role_key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_telegram_bot_token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456789")


# =============================================================================
# IMPORT APP
# =============================================================================
# La app se importa después de preparar env vars mínimas.
from app.main import app  # noqa: E402


# =============================================================================
# FIXTURES BASE
# =============================================================================

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """
    Fixture autouse para asegurar variables de entorno durante cada test.

    Aunque ya se definen arriba con os.environ.setdefault para cubrir import-time,
    este fixture garantiza valores controlados durante la ejecución de cada test.
    """
    monkeypatch.setenv("WEBHOOK_SECRET", "test_secret")
    monkeypatch.setenv(
        "SQS_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
    )
    monkeypatch.setenv("DATABRICKS_EXPORT_TARGET", "local")
    monkeypatch.setenv("ENABLE_DATABRICKS_EXPORT", "true")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test_supabase_service_role_key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_telegram_bot_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")


@pytest.fixture
def client():
    """Fixture para FastAPI TestClient."""
    return TestClient(app)


# =============================================================================
# MOCKS DE SERVICIOS EXTERNOS
# =============================================================================

@pytest.fixture
def mock_s3_upload(monkeypatch):
    """
    Mock para upload_text_to_s3 usado por databricks_export_service.

    Evita llamadas reales a S3 durante los tests.
    """
    from app.services import databricks_export_service

    mock_upload = MagicMock(
        return_value={
            "ok": True,
            "uploaded": True,
            "bucket": "test-bucket",
            "key": "test-key.jsonl",
        }
    )

    monkeypatch.setattr(
        databricks_export_service,
        "upload_text_to_s3",
        mock_upload,
        raising=False,
    )

    return mock_upload


@pytest.fixture
def mock_sqs_client(monkeypatch):
    """
    Mock para cliente SQS.

    Evita llamadas reales a AWS SQS durante los tests.
    """
    from app.services import sqs_queue_service

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {
        "MessageId": "test-message-id",
        "ResponseMetadata": {
            "HTTPStatusCode": 200,
        },
    }

    monkeypatch.setattr(
        sqs_queue_service,
        "get_sqs_client",
        lambda: mock_sqs,
        raising=False,
    )

    return mock_sqs


@pytest.fixture
def mock_supabase(monkeypatch):
    """
    Mock para cliente Supabase.

    Evita llamadas reales a Supabase durante los tests.
    """
    from app.repositories import supabase_repo

    mock_supabase = MagicMock()

    monkeypatch.setattr(
        supabase_repo,
        "supabase",
        mock_supabase,
        raising=False,
    )

    return mock_supabase


@pytest.fixture
def mock_binance_service(monkeypatch):
    """
    Mock para servicios de Binance.

    Evita llamadas reales a Binance durante los tests.
    """
    from app.services import binance_service

    mock_fetch_depth = AsyncMock(
        return_value={
            "bids": [],
            "asks": [],
        }
    )

    monkeypatch.setattr(
        binance_service,
        "fetch_depth",
        mock_fetch_depth,
        raising=False,
    )

    return mock_fetch_depth