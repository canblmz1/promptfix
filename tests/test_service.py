"""Tests for the local HTTP service."""

import json
from unittest.mock import MagicMock, patch

import pytest

from promptfix.service import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_has_cors(self, client):
        resp = client.get("/health")
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"


class TestConfigSafeEndpoint:
    def test_config_safe(self, client):
        resp = client.get("/config-safe")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "provider" in data
        assert "default_mode" in data

    def test_config_safe_no_api_key(self, client):
        """config-safe must never expose API keys."""
        resp = client.get("/config-safe")
        data = resp.get_json()
        for key in data:
            value = str(data[key]).lower()
            assert "api_key" not in value
            assert "secret" not in value


class TestOptimizeEndpoint:
    def test_empty_text_returns_400(self, client):
        resp = client.post("/optimize", json={"text": "", "mode": "short"})
        assert resp.status_code == 400

    def test_missing_text_returns_400(self, client):
        resp = client.post("/optimize", json={"mode": "short"})
        assert resp.status_code == 400

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_optimize_success(self, mock_config, mock_provider, client):
        mock_config.return_value = {
            "provider": "groq",
            "default_mode": "short",
            "providers": {"groq": {"model": "test"}},
            "validation": {"enabled": False},
            "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = (
            "Investigate and fix the login token refresh issue "
            "with minimal, targeted changes."
        )
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={
            "text": "login token refresh bozuldu başka yeri bozma",
            "mode": "short",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "optimized" in data
        assert "duration_ms" in data
        assert "valid" in data
        assert "mode" in data
        assert "provider" in data
        assert data["mode"] == "short"

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_optimize_returns_valid_field(self, mock_config, mock_provider, client):
        mock_config.return_value = {
            "provider": "groq",
            "default_mode": "short",
            "providers": {"groq": {"model": "test"}},
            "validation": {"enabled": False},
            "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the login bug with minimal changes."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix login", "mode": "short"})
        data = resp.get_json()
        assert isinstance(data["valid"], bool)

    def test_cors_preflight(self, client):
        resp = client.options("/optimize")
        assert resp.status_code in (200, 204)
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_service_token_auth(self, mock_config, mock_provider, client):
        """When service token is set, unauthorized requests get 401."""
        mock_config.return_value = {
            "provider": "groq",
            "default_mode": "short",
            "providers": {"groq": {"model": "test"}},
            "validation": {"enabled": False},
            "service": {"token": "my-secret-token"},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fixed."
        mock_provider.return_value = mock_prov

        # No auth header → 401
        resp = client.post("/optimize", json={"text": "fix login", "mode": "short"})
        assert resp.status_code == 401

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_service_token_auth_success(self, mock_config, mock_provider, client):
        """Correct token allows request."""
        mock_config.return_value = {
            "provider": "groq",
            "default_mode": "short",
            "providers": {"groq": {"model": "test"}},
            "validation": {"enabled": False},
            "service": {"token": "my-secret-token"},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the login issue."
        mock_provider.return_value = mock_prov

        resp = client.post(
            "/optimize",
            json={"text": "fix login", "mode": "short"},
            headers={"Authorization": "Bearer my-secret-token"},
        )
        assert resp.status_code == 200


class TestChatEndpoint:
    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_chat_creates_thread(self, mock_config, mock_provider, client):
        mock_config.return_value = {
            "provider": "groq",
            "default_mode": "short",
            "providers": {"groq": {"model": "test"}},
            "validation": {"enabled": False},
            "service": {"token": ""},
            "chat": {"default_mode": "short"},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Optimized prompt."
        mock_provider.return_value = mock_prov

        resp = client.post("/chat", json={"text": "fix login bug"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "content" in data
        assert "thread_id" in data
        assert data["status"] == "ok"
        assert data["mode"] == "short"

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_chat_empty_text(self, mock_config, mock_provider, client):
        mock_config.return_value = {
            "provider": "groq",
            "service": {"token": ""},
        }
        resp = client.post("/chat", json={"text": ""})
        assert resp.status_code == 400

    def test_list_threads(self, client):
        resp = client.get("/threads")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "threads" in data

    def test_delete_nonexistent_thread(self, client):
        resp = client.delete("/threads/nonexistent")
        assert resp.status_code == 404
