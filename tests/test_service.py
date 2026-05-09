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

    def test_health_has_cors_headers(self, client):
        """CORS method/header fields are always present; Allow-Origin is set only for allowed origins."""
        resp = client.get("/health", headers={"Origin": "http://127.0.0.1:3000"})
        assert resp.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:3000"
        assert "Content-Type" in resp.headers.get("Access-Control-Allow-Headers", "")


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

    def test_cors_preflight_from_extension(self, client):
        resp = client.options(
            "/optimize",
            headers={"Origin": "chrome-extension://abcdefg"},
        )
        assert resp.status_code in (200, 204)
        assert resp.headers.get("Access-Control-Allow-Origin") == "chrome-extension://abcdefg"
        assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")

    def test_cors_blocked_for_unknown_origin(self, client):
        resp = client.get(
            "/health",
            headers={"Origin": "https://evil.example.com"},
        )
        assert resp.headers.get("Access-Control-Allow-Origin") != "https://evil.example.com"

    def test_cors_allowed_for_localhost(self, client):
        resp = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"

    def test_optimize_text_too_long(self, client):
        long_text = "a" * 33_000
        resp = client.post("/optimize", json={"text": long_text, "mode": "short"})
        assert resp.status_code == 413

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
        """A valid UUID that doesn't exist returns 404; an invalid ID returns 400."""
        resp = client.delete("/threads/00000000-0000-4000-8000-000000000000")
        assert resp.status_code == 404

    def test_invalid_thread_id_rejected(self, client):
        """Thread ID that is not a UUID v4 must return 400."""
        resp = client.get("/threads/../../etc/passwd")
        assert resp.status_code in (400, 404)

    @patch("promptfix.service._get_config")
    def test_history_requires_auth_when_token_set(self, mock_config, client):
        """GET /history must return 401 when token is configured and missing."""
        mock_config.return_value = {
            "provider": "groq",
            "providers": {"groq": {"model": "test"}},
            "service": {"token": "secret"},
        }
        resp = client.get("/history")
        assert resp.status_code == 401

    @patch("promptfix.service._get_config")
    def test_history_delete_requires_auth_when_token_set(self, mock_config, client):
        """DELETE /history must return 401 when token is configured and missing."""
        mock_config.return_value = {
            "provider": "groq",
            "providers": {"groq": {"model": "test"}},
            "service": {"token": "secret"},
        }
        resp = client.delete("/history")
        assert resp.status_code == 401

    @patch("promptfix.service._get_config")
    def test_chat_text_too_long(self, mock_config, client):
        """Chat endpoint must reject oversized input."""
        mock_config.return_value = {
            "provider": "groq",
            "providers": {"groq": {"model": "test"}},
            "service": {"token": ""},
        }
        resp = client.post("/chat", json={"text": "x" * 33_000})
        assert resp.status_code == 413

    @patch("promptfix.service._get_config")
    def test_chat_invalid_thread_id_rejected(self, mock_config, client):
        """Chat with a non-UUID thread_id must return 400."""
        mock_config.return_value = {
            "provider": "groq",
            "providers": {"groq": {"model": "test"}},
            "service": {"token": ""},
        }
        resp = client.post("/chat", json={"text": "hello", "thread_id": "../../../etc"})
        assert resp.status_code == 400


class TestConfigReloadEndpoint:
    def test_reload_config_no_token(self, client):
        """POST /config/reload without a token (none configured) returns 200."""
        from unittest.mock import patch
        with patch("promptfix.service._get_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "groq", "service": {"token": ""}}
            with patch("promptfix.service.load_config") as mock_load:
                mock_load.return_value = {"provider": "groq", "service": {"token": ""}}
                resp = client.post("/config/reload")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "provider" in data

    def test_reload_config_blocked_without_token(self, client):
        """POST /config/reload must be 401 when token is set and not provided."""
        from unittest.mock import patch
        with patch("promptfix.service._get_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "groq", "service": {"token": "secret"}}
            resp = client.post("/config/reload")
        assert resp.status_code == 401
