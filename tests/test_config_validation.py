"""Tests for config validation."""

import pytest

from promptfix.config import _validate_config


class TestValidateConfig:
    def test_invalid_provider_raises(self):
        with pytest.raises(RuntimeError, match="Invalid provider"):
            _validate_config({"provider": "unknown_provider", "default_mode": "short"})

    def test_invalid_mode_raises(self):
        with pytest.raises(RuntimeError, match="Invalid default_mode"):
            _validate_config({"provider": "groq", "default_mode": "invalid_mode"})

    def test_valid_config_passes(self):
        # Should not raise
        _validate_config({"provider": "groq", "default_mode": "short"})

    def test_valid_ollama_provider(self):
        _validate_config({"provider": "ollama", "default_mode": "agent"})

    def test_valid_openai_compatible_provider(self):
        _validate_config({"provider": "openai_compatible", "default_mode": "raw"})

    def test_missing_provider_skips_validation(self):
        # Empty string or missing key should not raise
        _validate_config({"default_mode": "short"})

    def test_missing_mode_skips_validation(self):
        _validate_config({"provider": "groq"})
