"""Config management for PromptFix."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Load .env from project root or current directory
PROJECT_ROOT = Path(__file__).parent.parent
for _env_path in [PROJECT_ROOT / ".env", Path.cwd() / ".env"]:
    if _env_path.exists():
        load_dotenv(_env_path, override=True)
        break

DEFAULT_CONFIG = {
    "provider": "groq",
    "default_mode": "short",
    "providers": {
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "model": "llama-3.3-70b-versatile",
            "api_key_env": "GROQ_API_KEY",
            "timeout_seconds": 30,
        },
        "openai_compatible": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
            "api_key_env": "OPENAI_API_KEY",
            "timeout_seconds": 30,
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "qwen2.5:7b",
            "timeout_seconds": 60,
        },
    },
    "context": {
        "enabled": True,
        "mode_limits": {
            "raw": 0,
            "fast": 300,
            "short": 600,
            "agent": 1500,
            "explain": 3000,
        },
        "require_relevance": True,
    },
    "validation": {
        "enabled": True,
        "retry_on_invalid": True,
        "deterministic_fallback": True,
    },
    "hotkeys": {
        "fast": "ctrl+alt+f",
        "short": "ctrl+alt+s",
        "agent": "ctrl+alt+p",
        "raw": "ctrl+alt+r",
        "explain": "ctrl+alt+e",
    },
    "service": {
        "host": "127.0.0.1",
        "port": 52849,
        "token": "",
    },
    "chat": {
        "default_mode": "short",
        "max_context_messages": 10,
        "show_tokens": False,
    },
}


def get_config_dir() -> Path:
    return Path(os.environ.get("USERPROFILE", Path.home())) / ".promptfix"


def get_config_path() -> Path:
    return get_config_dir() / "config.yaml"


def load_config() -> dict[str, Any]:
    path = get_config_path()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        config = _deep_merge(DEFAULT_CONFIG, user_config)
    else:
        config = DEFAULT_CONFIG.copy()
    _validate_config(config)
    return config


_VALID_PROVIDERS = frozenset(DEFAULT_CONFIG["providers"].keys())
_VALID_MODES = frozenset(DEFAULT_CONFIG["context"]["mode_limits"].keys())


def _validate_config(config: dict[str, Any]) -> None:
    """Raise a descriptive RuntimeError if the config contains invalid values."""
    provider = config.get("provider", "")
    if provider and provider not in _VALID_PROVIDERS:
        raise RuntimeError(
            f"Invalid provider '{provider}' in config. "
            f"Valid options: {', '.join(sorted(_VALID_PROVIDERS))}."
        )

    default_mode = config.get("default_mode", "")
    if default_mode and default_mode not in _VALID_MODES:
        raise RuntimeError(
            f"Invalid default_mode '{default_mode}' in config. "
            f"Valid options: {', '.join(sorted(_VALID_MODES))}."
        )


def save_config(config: dict[str, Any]) -> None:
    import sys
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    if sys.platform != "win32":
        import stat
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def ensure_config() -> dict[str, Any]:
    path = get_config_path()
    if not path.exists():
        save_config(DEFAULT_CONFIG)
    return load_config()


def get_provider_config(config: dict[str, Any], provider_name: str | None = None) -> dict[str, Any]:
    name = provider_name or config.get("provider", "groq")
    providers = config.get("providers", {})
    return providers.get(name, {})


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
