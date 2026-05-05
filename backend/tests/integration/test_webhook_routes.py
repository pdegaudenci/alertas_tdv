"""
Tests de integración para webhook_routes.py.

Endpoints testeados:
- /api/webhook: responde rápido y agenda/manda a SQS mockeado.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


class TestWebhookRoutes:
    @patch("app.api.webhook_routes.send_alert_to_sqs", new_callable=AsyncMock)
    @patch("app.api.webhook_routes.persist_backend_error_log", new_callable=AsyncMock)
    def test_webhook_responde_rapido_y_agenda_sqs(self, mock_persist_error, mock_send_sqs, client: TestClient, mock_env_vars):
        """Test que /api/webhook responda rápido y mande a SQS mockeado."""
        mock_send_sqs.return_value = {"ok": True, "queued": True, "message_id": "test-id"}

        payload = {
            "secret": "test_secret",
            "signal": {
                "symbol": "BTCUSDC",
                "event": "LONG",
                "side": "BUY",
            },
            "message_type": "logical_event_full",
            "event_uid": "test-uid",
        }

        response = client.post(
            "/api/webhook",
            json=payload,
            headers={"x-webhook-secret": "test_secret"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        assert "Alert accepted quickly" in data["message"]
        assert data["trace_id"] is not None
        assert data["event_uid"] == "test-uid"
        assert data["message_type"] == "logical_event_full"
        assert data["event"] == "LONG"
        assert data["side"] == "BUY"
        assert data["symbol"] == "BTCUSDC"
        assert data["queue_backend"] == "sqs"
        assert data["background_processing"] is True

        # Verifica que se llamó a send_alert_to_sqs en background
        mock_send_sqs.assert_called_once_with(
            payload=payload,
            trace_id=data["trace_id"],
            source="tradingview_webhook_background"
        )

    @patch("app.api.webhook_routes.send_alert_to_sqs", new_callable=AsyncMock)
    def test_webhook_rechaza_sin_secret(self, mock_send_sqs, client: TestClient):
        """Test que rechace webhook sin secret válido."""
        payload = {"signal": {"symbol": "BTCUSDC"}}

        response = client.post("/api/webhook", json=payload)

        assert response.status_code == 401
        data = response.json()
        assert "missing webhook secret" in data["detail"]

        # No debería llamar a SQS
        mock_send_sqs.assert_not_called()

    @patch("app.api.webhook_routes.send_alert_to_sqs", new_callable=AsyncMock)
    @patch("app.api.webhook_routes.persist_backend_error_log", new_callable=AsyncMock)
    def test_webhook_maneja_error_sqs(self, mock_persist_error, mock_send_sqs, client: TestClient, mock_env_vars):
        """Test que maneje errores en SQS sin fallar la respuesta."""
        mock_send_sqs.return_value = {"ok": False, "error": "SQS failed"}

        payload = {
            "secret": "test_secret",
            "signal": {"symbol": "BTCUSDC"},
        }

        response = client.post(
            "/api/webhook",
            json=payload,
            headers={"x-webhook-secret": "test_secret"}
        )

        # La respuesta debería ser 200 (ACK rápido)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

        # Pero debería persistir el error
        mock_persist_error.assert_called_once()

    def test_webhook_debug_mode(self, client: TestClient, mock_env_vars):
        """Test modo debug del webhook."""
        payload = {
            "secret": "test_secret",
            "signal": {"symbol": "BTCUSDC"},
        }

        response = client.post(
            "/api/webhook?debug=1",
            json=payload,
            headers={"x-webhook-secret": "test_secret"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        assert "debug echo" in data["message"]
        assert "raw_body_text" in data
        assert "payload" in data</content>
<parameter name="filePath">c:\Users\sebastian\Desktop\trading_system\backend\tests\integration\test_webhook_routes.py