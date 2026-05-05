"""
Tests de integración para health_routes.py.

Endpoints testeados:
- /: responde OK con información del servicio.
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthRoutes:
    def test_health_endpoint_responde_ok(self, client: TestClient, mock_env_vars, mock_binance_service):
        """Test que / responda OK."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert data["ok"] is True
        assert "service" in data
        assert "timestamp" in data
        assert "routes" in data
        assert "binance_base_urls" in data
        assert "model_loaded" in data
        assert "allowed_origins" in data

        # Verifica que incluya rutas esperadas
        assert "/api/webhook" in data["routes"]
        assert "/api/health/binance" in data["routes"]

    def test_health_binance_endpoint(self, client: TestClient, mock_binance_service):
        """Test que /api/health/binance funcione."""
        response = client.get("/api/health/binance")

        assert response.status_code == 200
        data = response.json()

        # Debería tener bids y asks del mock
        assert "bids" in data
        assert "asks" in data

    def test_health_supabase_endpoint(self, client: TestClient, mock_supabase):
        """Test que /api/health/supabase funcione."""
        # Mock supabase query
        mock_supabase.table.return_value.select.return_value.execute.return_value.data = []

        response = client.get("/api/health/supabase")

        assert response.status_code == 200
        data = response.json()

        assert "ok" in data</content>
<parameter name="filePath">c:\Users\sebastian\Desktop\trading_system\backend\tests\integration\test_health_routes.py