"""Core rewriter: orchestrates intent -> template -> provider -> guard."""

from __future__ import annotations

import time

from promptfix.config import get_provider_config, load_config
from promptfix.context import build_context
from promptfix.guard import GuardResult, clean_output, get_fallback, validate_output
from promptfix.intent import Intent, parse_intent
from promptfix.providers.base import BaseProvider
from promptfix.providers.groq import GroqProvider
from promptfix.providers.ollama import OllamaProvider
from promptfix.providers.openai_compatible import OpenAICompatibleProvider
from promptfix.templates import build_retry_prompt, build_rewrite_prompt


class RewriteResult:
    def __init__(
        self,
        optimized: str,
        mode: str,
        provider: str,
        duration_ms: int,
        validation_status: str,
        intent: Intent | None = None,
    ):
        self.optimized = optimized
        self.mode = mode
        self.provider = provider
        self.duration_ms = duration_ms
        self.validation_status = validation_status
        self.intent = intent

    def to_dict(self) -> dict:
        return {
            "optimized": self.optimized,
            "mode": self.mode,
            "provider": self.provider,
            "duration_ms": self.duration_ms,
            "validation_status": self.validation_status,
            "valid": self.validation_status in ("valid", "unvalidated", "fallback"),
        }


def create_provider(config: dict | None = None, provider_name: str | None = None) -> BaseProvider:
    if config is None:
        config = load_config()
    name = provider_name or config.get("provider", "groq")
    pcfg = get_provider_config(config, name)

    if name == "groq":
        return GroqProvider(
            base_url=pcfg.get("base_url", "https://api.groq.com/openai/v1"),
            model=pcfg.get("model", "llama-3.3-70b-versatile"),
            api_key_env=pcfg.get("api_key_env", "GROQ_API_KEY"),
            api_key=pcfg.get("api_key"),
            timeout=pcfg.get("timeout_seconds", 30),
        )
    elif name == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=pcfg.get("base_url", "https://api.openai.com/v1"),
            model=pcfg.get("model", "gpt-4.1-mini"),
            api_key_env=pcfg.get("api_key_env", "OPENAI_API_KEY"),
            api_key=pcfg.get("api_key"),
            timeout=pcfg.get("timeout_seconds", 30),
        )
    elif name == "ollama":
        return OllamaProvider(
            base_url=pcfg.get("base_url", "http://localhost:11434"),
            model=pcfg.get("model", "qwen2.5:7b"),
            timeout=pcfg.get("timeout_seconds", 60),
        )
    else:
        raise RuntimeError(f"Unknown provider: {name}")


def _fallback_provider_names(config: dict, primary: str) -> list[str]:
    """Return providers to try after the primary fails, in config order."""
    all_providers = list(config.get("providers", {}).keys())
    return [p for p in all_providers if p != primary]


def rewrite(
    text: str,
    mode: str | None = None,
    config: dict | None = None,
    provider: BaseProvider | None = None,
    project_hints: dict | None = None,
    source: str = "unknown",
) -> RewriteResult:
    if config is None:
        config = load_config()
    if mode is None:
        mode = config.get("default_mode", "short")
    provider_name = config.get("provider", "groq")

    if provider is None:
        provider = create_provider(config)

    start = time.time()

    intent = parse_intent(text)
    context_lite = build_context(intent, mode, project_hints)
    messages = build_rewrite_prompt(text, intent, context_lite, mode)

    # --- Multi-provider fallback ---
    raw_output: str | None = None
    last_exc: Exception | None = None
    tried_providers = [provider_name]
    # Track the provider instance that succeeded so retry uses the same one
    active_provider = provider

    try:
        raw_output = provider.complete(messages)
    except Exception as exc:
        last_exc = exc

    if raw_output is None:
        for fallback_name in _fallback_provider_names(config, provider_name):
            try:
                fallback_provider = create_provider(config, fallback_name)
                raw_output = fallback_provider.complete(messages)
                provider_name = fallback_name  # report which provider actually responded
                active_provider = fallback_provider  # retry must use this provider
                tried_providers.append(fallback_name)
                last_exc = None
                break
            except Exception as exc:
                tried_providers.append(fallback_name)
                last_exc = exc

    if raw_output is None:
        raise RuntimeError(
            f"All providers failed: {', '.join(tried_providers)}. "
            f"Last error: {last_exc}"
        )

    cleaned = clean_output(raw_output)

    validation = config.get("validation", {})
    if validation.get("enabled", True):
        result = validate_output(cleaned, intent)
        if not result.valid and validation.get("retry_on_invalid", True):
            retry_messages = build_retry_prompt(text)
            raw_output = active_provider.complete(retry_messages)
            cleaned = clean_output(raw_output)
            result = validate_output(cleaned, intent)

        if not result.valid and validation.get("deterministic_fallback", True):
            cleaned = get_fallback(intent)
            status = "fallback"
        elif not result.valid:
            status = "invalid"
        else:
            status = "valid"
    else:
        status = "unvalidated"

    elapsed_ms = int((time.time() - start) * 1000)

    # Log to history
    try:
        from promptfix.history import log_entry
        log_entry(
            input_text=text,
            output_text=cleaned,
            mode=mode,
            provider=provider_name,
            duration_ms=elapsed_ms,
            validation_status=status,
            source=source,
        )
    except Exception:
        pass  # History logging must never break the pipeline

    return RewriteResult(
        optimized=cleaned,
        mode=mode,
        provider=provider_name,
        duration_ms=elapsed_ms,
        validation_status=status,
        intent=intent,
    )
