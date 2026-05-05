"""
Tests unitarios para databricks_export_service.py.

Funciones testeadas:
- build_databricks_bronze_event: genera campos top-level esperados.
- export_event_for_databricks: no llama realmente S3; mockea upload_text_to_s3.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.services.databricks_export_service import build_databricks_bronze_event, export_event_for_databricks


class TestBuildDatabricksBronzeEvent:
    def test_genera_campos_top_level_esperados(self):
        """Test que build_databricks_bronze_event genere campos top-level correctos."""
        payload = {
            "event_uid": "test-uid",
            "schema_version": "2.0",
            "message_type": "logical_event_full",
            "signal": {
                "symbol": "BTCUSDC",
                "tf": "1h",
                "event": "LONG",
                "side": "BUY",
                "price": 50000.0,
                "entry_price": 50000.0,
            },
            "trade_plan": {
                "tp_price": 51000.0,
                "sl_price": 49000.0,
                "tp_perc": 2.0,
                "sl_perc": 2.0,
                "rr_ratio": 1.0,
            },
        }

        validation = {
            "validation": {
                "approve": True,
                "confidence": 0.85,
                "probability_tp_before_sl": 0.7,
                "score_external": 0.9,
            },
        }

        result = build_databricks_bronze_event(payload, validation, trace_id="test-trace")

        # Campos top-level esperados
        assert result["event_uid"] == "test-uid"
        assert result["schema_version"] == "2.0"
        assert result["message_type"] == "logical_event_full"
        assert result["trace_id"] == "test-trace"
        assert result["symbol"] == "BTCUSDC"
        assert result["tf"] == "1h"
        assert result["event"] == "LONG"
        assert result["side"] == "BUY"
        assert result["price"] == 50000.0
        assert result["entry_price"] == 50000.0
        assert result["tp_price"] == 51000.0
        assert result["sl_price"] == 49000.0
        assert result["tp_perc"] == 2.0
        assert result["sl_perc"] == 2.0
        assert result["rr_ratio"] == 1.0
        assert result["validation_approve"] is True
        assert result["validation_confidence"] == 0.85
        assert result["probability_tp_before_sl"] == 0.7
        assert result["score_external"] == 0.9
        assert "raw_payload" in result
        assert "raw_validation" in result
        assert "ingestion_ts" in result
        assert "processing_date" in result
        assert result["source"] == "fastapi_trading_backend"
        assert result["lakehouse_layer"] == "bronze"

    def test_maneja_payload_sin_validation(self):
        """Test que funcione sin bloque de validation."""
        payload = {
            "signal": {"symbol": "BTCUSDC", "event": "LONG"},
        }

        result = build_databricks_bronze_event(payload)

        assert result["symbol"] == "BTCUSDC"
        assert result["event"] == "LONG"
        assert result["validation_approve"] is None
        assert result["raw_validation"] == {}


class TestExportEventForDatabricks:
    @patch("app.services.databricks_export_service.upload_text_to_s3")
    @patch("app.services.databricks_export_service.ENABLE_DATABRICKS_EXPORT", True)
    @patch("app.services.databricks_export_service.DATABRICKS_EXPORT_TARGET", "s3")
    def test_no_llama_realmente_s3(self, mock_upload):
        """Test que export_event_for_databricks no llame realmente a S3."""
        mock_upload.return_value = {"ok": True, "uploaded": True}

        payload = {
            "event_uid": "test-uid",
            "signal": {"symbol": "BTCUSDC"},
        }

        result = export_event_for_databricks(payload, trace_id="test-trace")

        # Verifica que se llamó al mock
        mock_upload.assert_called_once()
        assert result["ok"] is True
        assert result["exported"] is True

    @patch("app.services.databricks_export_service.ENABLE_DATABRICKS_EXPORT", False)
    def test_no_exporta_si_deshabilitado(self):
        """Test que no exporte si ENABLE_DATABRICKS_EXPORT=false."""
        payload = {"signal": {"symbol": "BTCUSDC"}}

        result = export_event_for_databricks(payload)

        assert result["ok"] is True
        assert result["exported"] is False
        assert result["reason"] == "ENABLE_DATABRICKS_EXPORT=false"

    @patch("app.services.databricks_export_service.ENABLE_DATABRICKS_EXPORT", True)
    @patch("app.services.databricks_export_service.DATABRICKS_EXPORT_TARGET", "local")
    def test_exporta_local_sin_s3(self):
        """Test que exporte a local sin llamar S3."""
        payload = {
            "event_uid": "test-uid",
            "signal": {"symbol": "BTCUSDC"},
        }

        result = export_event_for_databricks(payload, trace_id="test-trace")

        assert result["ok"] is True
        assert result["exported"] is True
        assert result["target"] == "local"</content>
<parameter name="filePath">c:\Users\sebastian\Desktop\trading_system\backend\tests\unit\test_databricks_export_service.py