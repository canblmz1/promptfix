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


class TestMultiProviderFallback:
    """F-01: Multi-provider fallback tests."""

    BASE_CONFIG = {
        "provider": "groq",
        "default_mode": "short",
        "validation": {"enabled": False},
        "providers": {
            "groq": {
                "base_url": "https://api.groq.com/openai/v1",
                "model": "llama-3.3-70b-versatile",
                "api_key_env": "GROQ_API_KEY",
                "timeout_seconds": 30,
            },
            "ollama": {
                "base_url": "http://localhost:11434",
                "model": "qwen2.5:7b",
                "timeout_seconds": 60,
            },
        },
    }

    def test_fallback_to_secondary_when_primary_fails(self):
        """If primary provider raises, fallback provider should be used."""
        primary_mock = MagicMock()
        primary_mock.complete.side_effect = RuntimeError("groq unavailable")

        fallback_mock = MagicMock()
        fallback_mock.complete.return_value = "Fix the token refresh bug."

        def _fake_create_provider(config, name=None):
            if name == "groq" or name is None:
                return primary_mock
            return fallback_mock

        with patch("promptfix.rewriter.create_provider", side_effect=_fake_create_provider):
            result = rewrite(
                text="fix login bug",
                mode="short",
                config=self.BASE_CONFIG,
                provider=None,
            )
        assert "token" in result.optimized.lower() or "bug" in result.optimized.lower()
        assert result.provider == "ollama"

    def test_all_providers_fail_raises_runtime_error(self):
        """When every provider fails, RuntimeError is raised listing all tried."""
        failing_mock = MagicMock()
        failing_mock.complete.side_effect = RuntimeError("unavailable")

        with patch("promptfix.rewriter.create_provider", return_value=failing_mock):
            with pytest.raises(RuntimeError, match="groq|ollama"):
                rewrite(
                    text="fix login bug",
                    mode="short",
                    config=self.BASE_CONFIG,
                    provider=None,
                )

    def test_primary_success_no_fallback_called(self):
        """When primary provider works, no fallback should be invoked."""
        primary_mock = MagicMock()
        primary_mock.complete.return_value = "Fix the login token refresh."

        call_log: list[str] = []

        def _fake_create_provider(config, name=None):
            resolved = name if name is not None else "groq"
            call_log.append(resolved)
            return primary_mock  # always primary — fallback should never be created

        with patch("promptfix.rewriter.create_provider", side_effect=_fake_create_provider):
            result = rewrite(
                text="fix login bug",
                mode="short",
                config=self.BASE_CONFIG,
                provider=None,
            )
        # "ollama" would appear in call_log only if fallback loop triggered
        assert "ollama" not in call_log, f"Fallback was invoked unexpectedly: {call_log}"
        assert result.provider == "groq"

    def test_fallback_retry_uses_fallback_provider_not_primary(self):
        """Regression: validation retry must use the successful fallback provider.

        When primary fails and fallback succeeds but output is invalid,
        the retry call must go to the fallback provider — NOT the broken primary.
        """
        primary_mock = MagicMock()
        primary_mock.complete.side_effect = RuntimeError("groq down")

        # Fallback returns invalid output on first call, valid on retry
        fallback_mock = MagicMock()
        fallback_mock.complete.side_effect = [
            "Project overview: this is a React application.",  # invalid — triggers retry
            "Investigate and fix the login token refresh with minimal, targeted changes.",  # valid retry
        ]

        def _fake_create_provider(config, name=None):
            if name == "groq" or name is None:
                return primary_mock
            return fallback_mock

        config = {
            "provider": "groq",
            "default_mode": "short",
            "validation": {
                "enabled": True,
                "retry_on_invalid": True,
                "deterministic_fallback": True,
            },
            "providers": {
                "groq": {
                    "base_url": "https://api.groq.com/openai/v1",
                    "model": "llama-3.3-70b-versatile",
                    "api_key_env": "GROQ_API_KEY",
                    "timeout_seconds": 30,
                },
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "model": "qwen2.5:7b",
                    "timeout_seconds": 60,
                },
            },
        }

        with patch("promptfix.rewriter.create_provider", side_effect=_fake_create_provider):
            result = rewrite(
                text="login token refresh bozuldu başka yeri bozma",
                mode="short",
                config=config,
                provider=None,
            )

        # Primary should have been tried exactly once (and raised RuntimeError)
        assert primary_mock.complete.call_count == 1, (
            f"Primary provider should have been tried once. Got: {primary_mock.complete.call_count}"
        )
        # Fallback should have been called twice: initial + retry
        assert fallback_mock.complete.call_count == 2, (
            f"Expected fallback to be called twice (initial + retry), "
            f"got {fallback_mock.complete.call_count}. "
            "If count is 1, retry went to the broken primary instead."
        )
        assert result.provider == "ollama"