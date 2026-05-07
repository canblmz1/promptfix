"""Tests for extension-related logic.

These test the Python-side behavior that the extension depends on.
The actual DOM replacement is JS-only and tested via the test page.
"""

import pytest
from unittest.mock import MagicMock, patch

from promptfix.service import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestExtensionServiceContract:
    """Test the /optimize API contract that the extension depends on."""

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_response_shape(self, mock_config, mock_provider, client):
        """Extension expects: optimized, mode, provider, duration_ms, valid"""
        mock_config.return_value = {
            "provider": "groq",
            "default_mode": "short",
            "providers": {"groq": {"model": "test"}},
            "validation": {"enabled": False},
            "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Optimized prompt text here."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={
            "text": "fix login bug",
            "mode": "short",
        })
        data = resp.get_json()

        # These are the fields the extension relies on
        assert "optimized" in data
        assert isinstance(data["optimized"], str)
        assert len(data["optimized"]) > 0

        assert "mode" in data
        assert data["mode"] in ("short", "agent", "raw")

        assert "provider" in data
        assert isinstance(data["provider"], str)

        assert "duration_ms" in data
        assert isinstance(data["duration_ms"], int)

        assert "valid" in data
        assert isinstance(data["valid"], bool)

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_short_mode(self, mock_config, mock_provider, client):
        mock_config.return_value = {
            "provider": "groq", "default_mode": "short",
            "providers": {"groq": {"model": "t"}},
            "validation": {"enabled": False}, "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Optimized."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix bug", "mode": "short"})
        assert resp.get_json()["mode"] == "short"

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_agent_mode(self, mock_config, mock_provider, client):
        mock_config.return_value = {
            "provider": "groq", "default_mode": "short",
            "providers": {"groq": {"model": "t"}},
            "validation": {"enabled": False}, "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Task:\nFix\nConstraints:\n- min"
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix bug", "mode": "agent"})
        assert resp.get_json()["mode"] == "agent"

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_raw_mode(self, mock_config, mock_provider, client):
        mock_config.return_value = {
            "provider": "groq", "default_mode": "short",
            "providers": {"groq": {"model": "t"}},
            "validation": {"enabled": False}, "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the login."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix login", "mode": "raw"})
        assert resp.get_json()["mode"] == "raw"

    def test_service_down_error_message(self, client):
        """When provider is broken, error must be clear."""
        # Reset cached provider to force re-init
        import promptfix.service as svc
        old_provider = svc._provider
        svc._provider = None
        svc._config = None

        resp = client.post("/optimize", json={"text": "fix bug", "mode": "short"})
        # May return 500 with error message
        if resp.status_code == 500:
            data = resp.get_json()
            assert "error" in data

        # Restore
        svc._provider = old_provider


class TestExtensionReplacementScenarios:
    """Test that the rewriter produces output suitable for replacement.
    These use the full pipeline with a mock provider to ensure the
    output is clean text (no fences, no prefixes, no quotes)."""

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def _optimize(self, text, mode, mock_config, mock_provider, client, provider_output):
        mock_config.return_value = {
            "provider": "groq", "default_mode": "short",
            "providers": {"groq": {"model": "t"}},
            "validation": {"enabled": False}, "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = provider_output
        mock_provider.return_value = mock_prov
        resp = client.post("/optimize", json={"text": text, "mode": mode})
        return resp.get_json()

    def test_textarea_replacement_clean(self, client):
        """Output for textarea must be clean text — no fences, no prefix."""
        with patch("promptfix.service._get_provider") as mp, \
             patch("promptfix.service._get_config") as mc:
            mc.return_value = {
                "provider": "groq", "default_mode": "short",
                "providers": {"groq": {"model": "t"}},
                "validation": {"enabled": False}, "service": {"token": ""},
            }
            prov = MagicMock()
            prov.complete.return_value = "Fix the login token refresh with minimal changes."
            mp.return_value = prov

            resp = client.post("/optimize", json={
                "text": "login bozuldu",
                "mode": "short",
            })
            optimized = resp.get_json()["optimized"]

            # Must not have fences, quotes, or prefixes
            assert not optimized.startswith("```")
            assert not optimized.startswith('"')
            assert not optimized.lower().startswith("here is")
            assert not optimized.lower().startswith("sure,")
