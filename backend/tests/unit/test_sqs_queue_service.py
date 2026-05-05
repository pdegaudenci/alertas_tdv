"""
Tests unitarios para sqs_queue_service.py.

Funciones testeadas:
- send_alert_to_sqs: no llama realmente AWS; mockea el cliente o función interna.
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.services.sqs_queue_service import send_alert_to_sqs


class TestSendAlertToSqs:
    @patch("app.services.sqs_queue_service.is_sqs_configured", return_value=True)
    @patch("app.services.sqs_queue_service.get_sqs_client")
    @patch("app.services.sqs_queue_service.SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/test-queue")
    @pytest.mark.asyncio
    async def test_no_llama_realmente_aws(self, mock_get_client, mock_is_configured):
        """Test que send_alert_to_sqs no llame realmente a AWS."""
        mock_sqs = AsyncMock()
        mock_sqs.send_message.return_value = {"MessageId": "test-message-id"}
        mock_get_client.return_value = mock_sqs

        payload = {
            "event_uid": "test-uid",
            "message_type": "logical_event_full",
            "signal": {"symbol": "BTCUSDC"},
        }

        result = await send_alert_to_sqs(payload, trace_id="test-trace")

        # Verifica que se llamó al mock
        mock_sqs.send_message.assert_called_once()
        assert result["ok"] is True
        assert result["queued"] is True
        assert result["message_id"] == "test-message-id"
        assert result["event_uid"] == "test-uid"
        assert result["message_type"] == "logical_event_full"

    @patch("app.services.sqs_queue_service.is_sqs_configured", return_value=False)
    @pytest.mark.asyncio
    async def test_no_envia_si_no_configurado(self, mock_is_configured):
        """Test que no envíe si SQS no está configurado."""
        payload = {"signal": {"symbol": "BTCUSDC"}}

        result = await send_alert_to_sqs(payload, trace_id="test-trace")

        assert result["ok"] is False
        assert result["queued"] is False
        assert result["reason"] == "SQS_QUEUE_URL_not_configured"

    @patch("app.services.sqs_queue_service.is_sqs_configured", return_value=True)
    @patch("app.services.sqs_queue_service.get_sqs_client")
    @patch("app.services.sqs_queue_service.SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/test-queue")
    @pytest.mark.asyncio
    async def test_maneja_error_en_envio(self, mock_get_client, mock_is_configured):
        """Test que maneje errores en el envío."""
        mock_sqs = AsyncMock()
        mock_sqs.send_message.side_effect = Exception("AWS Error")
        mock_get_client.return_value = mock_sqs

        payload = {"signal": {"symbol": "BTCUSDC"}}

        result = await send_alert_to_sqs(payload, trace_id="test-trace")

        assert result["ok"] is False
        assert result["queued"] is False
        assert "AWS Error" in result["error"]</content>
<parameter name="filePath">c:\Users\sebastian\Desktop\trading_system\backend\tests\unit\test_sqs_queue_service.py