"""Groq provider (OpenAI-compatible, optimized for speed)."""

from __future__ import annotations

import json
import os
from collections.abc import Generator

import requests

from promptfix.providers.base import BaseProvider


class GroqProvider(BaseProvider):
    def __init__(self, base_url: str, model: str, api_key_env: str | None = None, api_key: str | None = None, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        # Support direct api_key, env var from .env, or system env var
        if api_key:
            self.api_key = api_key
        elif api_key_env:
            self.api_key = os.environ.get(api_key_env, "")
        else:
            self.api_key = ""
        if not self.api_key:
            raise RuntimeError(
                f"Missing API key. Use one of:\n"
                f'  1. Create .env file: GROQ_API_KEY=your_key\n'
                f'  2. Environment variable: setx GROQ_API_KEY "your_key"\n'
                f'  3. Config: api_key: your_key (in ~/.promptfix/config.yaml)'
            )

    def complete(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        if resp.status_code == 401:
            raise RuntimeError("Groq API unauthorized. Check your API key.")
        if resp.status_code == 429:
            raise RuntimeError("Groq API rate limit exceeded. Wait and retry.")
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""

    def stream_complete(
        self, messages: list[dict[str, str]], temperature: float = 0.2
    ) -> Generator[str, None, None]:
        """Stream completion chunks using SSE."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
            "stream": True,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout, stream=True)
        if resp.status_code == 401:
            raise RuntimeError("Groq API unauthorized. Check your API key.")
        if resp.status_code == 429:
            raise RuntimeError("Groq API rate limit exceeded. Wait and retry.")
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue

    def health_check(self) -> tuple[bool, str]:
        try:
            url = f"{self.base_url}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return True, f"Groq OK ({self.model})"
            if resp.status_code == 401:
                return False, "Unauthorized. Check API key."
            return False, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)
