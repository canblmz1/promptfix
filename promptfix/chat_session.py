"""Chat session (thread) management for PromptFix Chat.

Similar to Discord threads: each conversation is a thread with ID,
messages, mode history, and metadata. Threads are persisted as JSON.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from promptfix.config import get_config_dir

THREADS_DIR = get_config_dir() / "threads"
MAX_MESSAGES_PER_THREAD = 100


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system"
    content: str
    mode: str = "short"
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "mode": self.mode,
            "timestamp": self.timestamp or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ChatMessage:
        return cls(
            role=d.get("role", "user"),
            content=d.get("content", ""),
            mode=d.get("mode", "short"),
            timestamp=d.get("timestamp", ""),
            metadata=d.get("metadata", {}),
        )


@dataclass
class ChatThread:
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessage] = field(default_factory=list)
    current_mode: str = "short"
    provider: str = "groq"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
            "current_mode": self.current_mode,
            "provider": self.provider,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ChatThread:
        return cls(
            id=d.get("id", ""),
            title=d.get("title", "Untitled"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            messages=[ChatMessage.from_dict(m) for m in d.get("messages", [])],
            current_mode=d.get("current_mode", "short"),
            provider=d.get("provider", "groq"),
        )

    def add_message(self, role: str, content: str, mode: str | None = None, metadata: dict | None = None):
        """Add a message and trim if over limit."""
        msg = ChatMessage(
            role=role,
            content=content,
            mode=mode or self.current_mode,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            metadata=metadata or {},
        )
        self.messages.append(msg)
        self.updated_at = msg.timestamp

        # Auto-title from first user message
        if role == "user" and self.title == "Untitled" and content.strip():
            words = content.strip().split()[:6]
            self.title = " ".join(words) + ("..." if len(content.split()) > 6 else "")

        # Trim old messages
        if len(self.messages) > MAX_MESSAGES_PER_THREAD:
            self.messages = self.messages[-MAX_MESSAGES_PER_THREAD:]

    def get_context_messages(self, limit: int = 10) -> list[dict[str, str]]:
        """Return recent messages formatted for provider API."""
        recent = self.messages[-limit:]
        return [
            {"role": m.role, "content": m.content}
            for m in recent
            if m.role in ("user", "assistant", "system")
        ]

    def set_mode(self, mode: str):
        self.current_mode = mode


# --- Persistence ---

def _threads_dir() -> Path:
    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    return THREADS_DIR


def _thread_path(thread_id: str) -> Path:
    return _threads_dir() / f"{thread_id}.json"


def save_thread(thread: ChatThread) -> None:
    path = _thread_path(thread.id)
    path.write_text(json.dumps(thread.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def load_thread(thread_id: str) -> ChatThread | None:
    path = _thread_path(thread_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ChatThread.from_dict(data)


def create_thread(mode: str = "short", provider: str = "groq", title: str = "Untitled") -> ChatThread:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    thread = ChatThread(
        id=str(uuid.uuid4()),
        title=title,
        created_at=now,
        updated_at=now,
        current_mode=mode,
        provider=provider,
    )
    save_thread(thread)
    return thread


def list_threads() -> list[ChatThread]:
    threads = []
    for path in _threads_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            threads.append(ChatThread.from_dict(data))
        except Exception:
            continue
    return sorted(threads, key=lambda t: t.updated_at, reverse=True)


def delete_thread(thread_id: str) -> bool:
    path = _thread_path(thread_id)
    if path.exists():
        path.unlink()
        return True
    return False
