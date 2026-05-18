"""Base provider interface."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any

import requests


class BaseProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        ...

    @abstractmethod
    def health_check(self) -> tuple[bool, str]:
        ...

    def stream_complete(
        self, messages: list[dict[str, str]], temperature: float = 0.2
    ) -> Generator[str, None, None]:
        """Yield partial content chunks as they arrive.

        Default implementation falls back to complete() and yields the full result.
        Providers should override this for true streaming.
        """
        yield self.complete(messages, temperature)


class OpenAILikeProvider(BaseProvider):
    """Shared implementation for OpenAI-compatible REST APIs (Groq, OpenAI, etc.).

    Subclasses only need to provide ``provider_name`` and optionally
    override ``_handle_error_status`` for provider-specific error messages.
    """

    provider_name: str = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key_env: str | None = None,
        api_key: str | None = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        if api_key:
            self.api_key = api_key
        elif api_key_env:
            self.api_key = os.environ.get(api_key_env, "")
        else:
            self.api_key = ""
        if not self.api_key:
            env_hint = api_key_env or "YOUR_API_KEY"
            raise RuntimeError(
                f"Missing API key for {self.provider_name}. Use one of:\n"
                f"  1. Create .env file: {env_hint}=your_key\n"
                f'  2. Environment variable: setx {env_hint} "your_key"\n'
                f"  3. Config: api_key: your_key (in ~/.promptfix/config.yaml)"
            )

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _handle_error_status(self, status_code: int) -> None:
        """Raise a descriptive RuntimeError for known error codes."""
        if status_code == 401:
            raise RuntimeError(f"{self.provider_name} API unauthorized. Check your API key.")
        if status_code == 429:
            raise RuntimeError(f"{self.provider_name} API rate limit exceeded. Wait and retry.")

    def complete(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }
        resp = requests.post(url, headers=self._auth_headers(), json=payload, timeout=self.timeout)
        self._handle_error_status(resp.status_code)
        resp.raise_for_status()
        choices = resp.json().get("choices", [])
        return choices[0].get("message", {}).get("content", "") if choices else ""

    def stream_complete(
        self, messages: list[dict[str, str]], temperature: float = 0.2
    ) -> Generator[str, None, None]:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
            "stream": True,
        }
        resp = requests.post(
            url, headers=self._auth_headers(), json=payload, timeout=self.timeout, stream=True
        )
        self._handle_error_status(resp.status_code)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8")
            if decoded.startswith("data: "):
                data_str = decoded[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue

    def health_check(self) -> tuple[bool, str]:
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return True, f"{self.provider_name} OK ({self.model})"
            if resp.status_code == 401:
                return False, "Unauthorized. Check API key."
            return False, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)
