"""Tests for provider initialization and behavior."""

import os
from unittest.mock import MagicMock, patch

import pytest

from promptfix.providers.base import BaseProvider
from promptfix.providers.groq import GroqProvider
from promptfix.providers.ollama import OllamaProvider
from promptfix.providers.openai_compatible import OpenAICompatibleProvider


class TestGroqProvider:
    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GROQ_API_KEY", None)
            with pytest.raises(RuntimeError, match="Missing API key"):
                GroqProvider(
                    base_url="https://api.groq.com/openai/v1",
                    model="llama-3.3-70b-versatile",
                    api_key_env="GROQ_API_KEY",
                )

    def test_init_with_key(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
            provider = GroqProvider(
                base_url="https://api.groq.com/openai/v1",
                model="llama-3.3-70b-versatile",
                api_key_env="GROQ_API_KEY",
            )
            assert provider.model == "llama-3.3-70b-versatile"
            assert provider.api_key == "test-key"

    @patch("promptfix.providers.base.requests.post")
    def test_complete_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Optimized prompt here"}}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
            provider = GroqProvider(
                base_url="https://api.groq.com/openai/v1",
                model="llama-3.3-70b-versatile",
                api_key_env="GROQ_API_KEY",
            )
            result = provider.complete([{"role": "user", "content": "test"}])
            assert result == "Optimized prompt here"

    @patch("promptfix.providers.base.requests.post")
    def test_complete_unauthorized(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = Exception("401")
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"GROQ_API_KEY": "bad-key"}):
            provider = GroqProvider(
                base_url="https://api.groq.com/openai/v1",
                model="llama-3.3-70b-versatile",
                api_key_env="GROQ_API_KEY",
            )
            with pytest.raises(RuntimeError, match="unauthorized"):
                provider.complete([{"role": "user", "content": "test"}])

    @patch("promptfix.providers.base.requests.post")
    def test_stream_complete(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = [
            b'data: {"choices": [{"delta": {"content": "Hello "}}]}',
            b'data: {"choices": [{"delta": {"content": "world"}}]}',
            b'data: [DONE]',
        ]
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
            provider = GroqProvider(
                base_url="https://api.groq.com/openai/v1",
                model="llama-3.3-70b-versatile",
                api_key_env="GROQ_API_KEY",
            )
            chunks = list(provider.stream_complete([{"role": "user", "content": "test"}]))
            assert chunks == ["Hello ", "world"]


class TestOllamaProvider:
    def test_init_defaults(self):
        provider = OllamaProvider()
        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "qwen2.5:7b"

    def test_custom_config(self):
        provider = OllamaProvider(
            base_url="http://localhost:11435",
            model="llama3:8b",
        )
        assert provider.base_url == "http://localhost:11435"
        assert provider.model == "llama3:8b"

    @patch("promptfix.providers.ollama.requests.post")
    def test_stream_complete(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = [
            b'{"message": {"content": "Hello "}, "done": false}',
            b'{"message": {"content": "world"}, "done": false}',
            b'{"message": {"content": "!"}, "done": true}',
        ]
        mock_post.return_value = mock_resp

        provider = OllamaProvider()
        chunks = list(provider.stream_complete([{"role": "user", "content": "test"}]))
        assert chunks == ["Hello ", "world"]


class TestOpenAICompatibleProvider:
    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(RuntimeError, match="Missing API key"):
                OpenAICompatibleProvider(
                    base_url="https://api.openai.com/v1",
                    model="gpt-4.1-mini",
                    api_key_env="OPENAI_API_KEY",
                )

    @patch("promptfix.providers.base.requests.post")
    def test_stream_complete(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = [
            b'data: {"choices": [{"delta": {"content": "First "}}]}',
            b'data: {"choices": [{"delta": {"content": "chunk"}}]}',
            b'data: [DONE]',
        ]
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAICompatibleProvider(
                base_url="https://api.openai.com/v1",
                model="gpt-4.1-mini",
                api_key_env="OPENAI_API_KEY",
            )
            chunks = list(provider.stream_complete([{"role": "user", "content": "test"}]))
            assert chunks == ["First ", "chunk"]


class TestBaseProvider:
    def test_stream_complete_fallback(self):
        """BaseProvider.stream_complete falls back to complete()."""
        class DummyProvider(BaseProvider):
            def complete(self, messages, temperature=0.2):
                return "fallback result"
            def health_check(self):
                return True, "ok"

        provider = DummyProvider()
        chunks = list(provider.stream_complete([{"role": "user", "content": "test"}]))
        assert chunks == ["fallback result"]
