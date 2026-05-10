"""OpenAI-compatible provider."""

from __future__ import annotations

from promptfix.providers.base import OpenAILikeProvider


class OpenAICompatibleProvider(OpenAILikeProvider):
    provider_name = "OpenAI-compatible"
