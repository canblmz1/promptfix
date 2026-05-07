"""Tests for the rewriter orchestrator."""

from unittest.mock import MagicMock, patch

import pytest

from promptfix.rewriter import RewriteResult, create_provider, rewrite


class TestCreateProvider:
    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"})
    def test_create_groq(self):
        config = {
            "provider": "groq",
            "providers": {
                "groq": {
                    "base_url": "https://api.groq.com/openai/v1",
                    "model": "llama-3.3-70b-versatile",
                    "api_key_env": "GROQ_API_KEY",
                    "timeout_seconds": 30,
                },
            },
        }
        provider = create_provider(config, "groq")
        assert provider.model == "llama-3.3-70b-versatile"

    def test_create_ollama(self):
        config = {
            "provider": "ollama",
            "providers": {
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "model": "qwen2.5:7b",
                    "timeout_seconds": 60,
                },
            },
        }
        provider = create_provider(config, "ollama")
        assert provider.model == "qwen2.5:7b"

    def test_unknown_provider_raises(self):
        with pytest.raises(RuntimeError, match="Unknown provider"):
            create_provider({"provider": "nonexistent", "providers": {}}, "nonexistent")


class TestRewrite:
    def test_rewrite_with_mock_provider(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = (
            "Investigate and fix the login token refresh issue with minimal, "
            "targeted changes. Inspect the existing auth flow first."
        )

        config = {
            "provider": "groq",
            "default_mode": "short",
            "validation": {"enabled": True, "retry_on_invalid": True, "deterministic_fallback": True},
        }

        result = rewrite(
            text="login token refresh bozuldu başka yeri bozma",
            mode="short",
            config=config,
            provider=mock_provider,
        )

        assert isinstance(result, RewriteResult)
        assert result.mode == "short"
        assert result.duration_ms >= 0
        assert "login" in result.optimized.lower() or "auth" in result.optimized.lower() or "token" in result.optimized.lower()

    def test_fallback_on_invalid_output(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "Project overview: this is a React app."

        config = {
            "provider": "groq",
            "default_mode": "short",
            "validation": {"enabled": True, "retry_on_invalid": True, "deterministic_fallback": True},
        }

        result = rewrite(
            text="login token refresh bozuldu",
            mode="short",
            config=config,
            provider=mock_provider,
        )

        assert result.validation_status == "fallback"
        assert "Investigate" in result.optimized or "fix" in result.optimized.lower()

    def test_to_dict_has_valid_field(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = (
            "Fix the login token refresh with minimal, targeted changes."
        )

        config = {
            "provider": "groq",
            "default_mode": "short",
            "validation": {"enabled": True, "retry_on_invalid": True, "deterministic_fallback": True},
        }

        result = rewrite(
            text="login token refresh bozuldu başka yeri bozma",
            mode="short",
            config=config,
            provider=mock_provider,
        )

        d = result.to_dict()
        assert "valid" in d
        assert isinstance(d["valid"], bool)
        assert "optimized" in d
        assert "mode" in d
        assert "provider" in d
        assert "duration_ms" in d

    def test_raw_mode_skips_context(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "Fix the login bug."

        config = {
            "provider": "groq",
            "default_mode": "short",
            "validation": {"enabled": False},
        }

        result = rewrite(
            text="fix the login bug",
            mode="raw",
            config=config,
            provider=mock_provider,
        )
        assert result.mode == "raw"

    def test_agent_mode(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = (
            "Task:\nFix the login token refresh\n\n"
            "Context:\nauth module\n\n"
            "Instructions:\n- Inspect flow\n\n"
            "Constraints:\n- Minimal changes\n\n"
            "Validation:\n- Run tests\n\n"
            "Deliverables:\n- Working refresh"
        )

        config = {
            "provider": "groq",
            "default_mode": "short",
            "validation": {"enabled": False},
        }

        result = rewrite(
            text="login token refresh bozuldu",
            mode="agent",
            config=config,
            provider=mock_provider,
        )
        assert result.mode == "agent"
        assert "Task:" in result.optimized
