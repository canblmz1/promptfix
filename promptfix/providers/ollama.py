"""Ollama provider (local models)."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

import requests

from promptfix.providers.base import BaseProvider


class OllamaProvider(BaseProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b", timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        resp = requests.post(url, json=payload, timeout=self.timeout)
        if resp.status_code == 404:
            raise RuntimeError(f"Ollama model '{self.model}' not found. Run: ollama pull {self.model}")
        resp.raise_for_status()
        data = resp.json()
        return str(data.get("message", {}).get("content", ""))

    def stream_complete(
        self, messages: list[dict[str, str]], temperature: float = 0.2
    ) -> Generator[str, None, None]:
        """Stream completion chunks from Ollama."""
        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        resp = requests.post(url, json=payload, timeout=self.timeout, stream=True)
        if resp.status_code == 404:
            raise RuntimeError(f"Ollama model '{self.model}' not found. Run: ollama pull {self.model}")
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line.decode("utf-8"))
                if data.get("done"):
                    break
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

    def health_check(self) -> tuple[bool, str]:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if self.model in models or any(self.model in m for m in models):
                    return True, f"Ollama OK ({self.model})"
                return False, f"Ollama running but model '{self.model}' not found. Available: {', '.join(models[:5])}"
            return False, f"Ollama HTTP {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to Ollama. Is it running?"
        except Exception as e:
            return False, str(e)
