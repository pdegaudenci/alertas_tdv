"""
Tests unitarios para security.py.

Funciones testeadas:
- validate_secret: acepta secret válido y rechaza inválido.
"""

import pytest
from fastapi import HTTPException
from app.core.security import validate_secret


class TestValidateSecret:
    def test_acepta_secret_valido_header(self, monkeypatch):
        """Test que acepte secret válido en header x-webhook-secret."""
        monkeypatch.setenv("WEBHOOK_SECRET", "valid_secret")

        # No debería lanzar excepción
        validate_secret(x_webhook_secret="valid_secret")

    def test_acepta_secret_valido_payload(self, monkeypatch):
        """Test que acepte secret válido en payload.secret."""
        monkeypatch.setenv("WEBHOOK_SECRET", "valid_secret")

        # No debería lanzar excepción
        validate_secret(payload_secret="valid_secret")

    def test_rechaza_secret_invalido(self, monkeypatch):
        """Test que rechace secret inválido."""
        monkeypatch.setenv("WEBHOOK_SECRET", "valid_secret")

        with pytest.raises(HTTPException) as exc_info:
            validate_secret(x_webhook_secret="invalid_secret")

        assert exc_info.value.status_code == 401
        assert "invalid webhook secret" in exc_info.value.detail

    def test_rechaza_sin_secret(self, monkeypatch):
        """Test que rechace cuando no se proporciona secret."""
        monkeypatch.setenv("WEBHOOK_SECRET", "valid_secret")

        with pytest.raises(HTTPException) as exc_info:
            validate_secret()

        assert exc_info.value.status_code == 401
        assert "missing webhook secret" in exc_info.value.detail

    def test_no_bloquea_sin_webhook_secret_configurado(self, monkeypatch):
        """Test que no bloquee si WEBHOOK_SECRET no está configurado."""
        monkeypatch.delenv("WEBHOOK_SECRET", raising=False)

        # No debería lanzar excepción
        validate_secret(x_webhook_secret="any_secret")

    def test_prefiere_header_sobre_payload(self, monkeypatch):
        """Test que prefiera header x-webhook-secret sobre payload.secret."""
        monkeypatch.setenv("WEBHOOK_SECRET", "valid_secret")

        # Header válido, payload inválido -> debería aceptar
        validate_secret(x_webhook_secret="valid_secret", payload_secret="invalid")

        # Header inválido, payload válido -> debería rechazar
        with pytest.raises(HTTPException):
            validate_secret(x_webhook_secret="invalid", payload_secret="valid_secret")</content>
<parameter name="filePath">c:\Users\sebastian\Desktop\trading_system\backend\tests\unit\test_security.py