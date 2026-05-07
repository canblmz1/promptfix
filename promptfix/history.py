"""Prompt history: log every optimization for review."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from promptfix.config import get_config_dir


MAX_HISTORY = 200


def _history_path() -> Path:
    return get_config_dir() / "history.jsonl"


def log_entry(
    input_text: str,
    output_text: str,
    mode: str,
    provider: str,
    duration_ms: int,
    validation_status: str,
    source: str = "unknown",
) -> None:
    """Append one entry to the history log."""
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "input": input_text[:500],
        "output": output_text[:1000],
        "mode": mode,
        "provider": provider,
        "ms": duration_ms,
        "status": validation_status,
        "source": source,
    }
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Trim if too long
    _trim_history(path)


def get_history(limit: int = 20) -> list[dict[str, Any]]:
    """Return last N history entries, newest first."""
    path = _history_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    entries = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(entries) >= limit:
            break
    return entries


def clear_history() -> int:
    """Delete all history. Returns count deleted."""
    path = _history_path()
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    count = len([l for l in lines if l.strip()])
    path.unlink()
    return count


def _trim_history(path: Path) -> None:
    """Keep only the last MAX_HISTORY entries."""
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    if len(lines) > MAX_HISTORY:
        keep = lines[-MAX_HISTORY:]
        path.write_text("\n".join(keep) + "\n", encoding="utf-8")
