"""Prompt snippet library for chat.

Snippets are reusable prompt fragments that can be saved and recalled
with slash commands like /snippet add <name> <content>.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from promptfix.config import get_config_dir

SNIPPETS_FILE = get_config_dir() / "snippets.json"


def _load_snippets() -> dict[str, str]:
    if not SNIPPETS_FILE.exists():
        return {}
    try:
        data = json.loads(SNIPPETS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_snippets(snippets: dict[str, str]) -> None:
    SNIPPETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SNIPPETS_FILE.write_text(
        json.dumps(snippets, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_snippet(name: str, content: str) -> bool:
    """Add or overwrite a snippet."""
    if not name or not content:
        return False
    snippets = _load_snippets()
    snippets[name] = content
    _save_snippets(snippets)
    return True


def get_snippet(name: str) -> str | None:
    """Get snippet content by name."""
    snippets = _load_snippets()
    return snippets.get(name)


def delete_snippet(name: str) -> bool:
    """Delete a snippet by name."""
    snippets = _load_snippets()
    if name in snippets:
        del snippets[name]
        _save_snippets(snippets)
        return True
    return False


def list_snippets() -> list[tuple[str, str]]:
    """List all snippets as (name, preview) tuples."""
    snippets = _load_snippets()
    items = []
    for name, content in snippets.items():
        preview = content[:60].replace("\n", " ")
        if len(content) > 60:
            preview += "..."
        items.append((name, preview))
    return sorted(items, key=lambda x: x[0].lower())


def expand_snippets(text: str) -> str:
    """Replace :snippet_name: in text with snippet content."""
    snippets = _load_snippets()
    result = text
    for name, content in snippets.items():
        placeholder = f":{name}:"
        if placeholder in result:
            result = result.replace(placeholder, content)
    return result
