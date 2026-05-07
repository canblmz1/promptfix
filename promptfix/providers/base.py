"""Base provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator


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
