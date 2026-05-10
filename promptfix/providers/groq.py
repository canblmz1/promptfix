"""Groq provider (OpenAI-compatible, optimized for speed)."""

from __future__ import annotations

from promptfix.providers.base import OpenAILikeProvider


class GroqProvider(OpenAILikeProvider):
    provider_name = "Groq"

    def _handle_error_status(self, status_code: int) -> None:
        if status_code == 401:
            raise RuntimeError("Groq API unauthorized. Check your API key.")
        if status_code == 429:
            raise RuntimeError("Groq API rate limit exceeded. Wait and retry.")
