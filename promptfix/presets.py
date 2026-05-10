"""Built-in prompt presets for common coding scenarios.

Usage in CLI:  promptfix preset list
               promptfix preset use <name> "your raw text"
Usage in chat: /preset <name>
"""

from __future__ import annotations

from pathlib import Path
import json

# ---------------------------------------------------------------------------
# Built-in presets
# ---------------------------------------------------------------------------

BUILTIN_PRESETS: dict[str, dict[str, str]] = {
    "bugfix-minimal": {
        "description": "Minimal targeted bug fix — no unrelated changes",
        "mode": "short",
        "system_hint": (
            "Focus: reproduce → root cause → minimal fix → verify. "
            "Do NOT refactor, rename, or touch unrelated code."
        ),
    },
    "perf-audit": {
        "description": "Performance investigation and targeted optimization",
        "mode": "agent",
        "system_hint": (
            "Profile first, optimize the measured bottleneck only. "
            "Show before/after complexity. Avoid premature optimization."
        ),
    },
    "security-review": {
        "description": "Security audit: OWASP Top 10 + common vulnerabilities",
        "mode": "agent",
        "system_hint": (
            "Check: injection, broken auth, XSS, IDOR, misconfiguration, "
            "secrets in code. Report severity (Critical/High/Medium/Low). "
            "Suggest fix for each finding."
        ),
    },
    "feature-spec": {
        "description": "Turn a vague feature idea into a structured implementation spec",
        "mode": "agent",
        "system_hint": (
            "Output: Problem statement, Acceptance criteria, "
            "Technical approach, Edge cases, Test plan."
        ),
    },
    "test-coverage": {
        "description": "Write comprehensive tests for existing code",
        "mode": "agent",
        "system_hint": (
            "Cover: happy path, edge cases, error paths, boundary values. "
            "Use the project's existing test framework and conventions."
        ),
    },
    "refactor-safe": {
        "description": "Safe refactor — preserve behavior, improve readability",
        "mode": "short",
        "system_hint": (
            "Preserve ALL existing behavior. Add tests before changing. "
            "Small, reviewable commits. No big bang rewrites."
        ),
    },
    "deploy-checklist": {
        "description": "Pre-deployment checklist and release prompt",
        "mode": "agent",
        "system_hint": (
            "Cover: env vars, migrations, rollback plan, health checks, "
            "monitoring alerts, feature flags, smoke tests."
        ),
    },
    "code-review": {
        "description": "Structured code review with actionable feedback",
        "mode": "agent",
        "system_hint": (
            "Review: correctness, security, performance, readability, tests. "
            "Group by severity. Suggest concrete improvements."
        ),
    },
    "agent-safety-checklist": {
        "description": "Safe coding-agent task: read first, plan, minimal changes, verify",
        "mode": "agent",
        "system_hint": (
            "SAFETY CHECKLIST — the agent MUST follow this order:\n"
            "1. READ relevant files before writing any code.\n"
            "2. PLAN: produce a short bullet-point plan before implementing.\n"
            "3. CHANGE only the minimum files necessary. Do not touch unrelated code.\n"
            "4. PROTECT secrets, API keys, environment variables, and production config — "
            "never modify them.\n"
            "5. NO large refactors unless explicitly requested.\n"
            "6. FLAG any database migration, breaking API change, or dependency upgrade "
            "explicitly before proceeding.\n"
            "7. RUN existing tests (or the project's test command) after the change.\n"
            "8. REPORT: list changed files, test outcome, and any identified risks."
        ),
    },
}

# ---------------------------------------------------------------------------
# User presets (stored in ~/.promptfix/presets.json)
# ---------------------------------------------------------------------------

def _get_presets_file() -> Path:
    from promptfix.config import get_config_dir
    return get_config_dir() / "presets.json"


def _load_user_presets() -> dict[str, dict[str, str]]:
    path = _get_presets_file()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_user_presets(presets: dict[str, dict[str, str]]) -> None:
    path = _get_presets_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")


def list_presets() -> list[tuple[str, str, str]]:
    """Return list of (name, description, source) for all presets."""
    result = []
    for name, meta in BUILTIN_PRESETS.items():
        result.append((name, meta["description"], "builtin"))
    for name, meta in _load_user_presets().items():
        result.append((name, meta.get("description", ""), "user"))
    return result


def get_preset(name: str) -> dict[str, str] | None:
    """Return preset dict or None if not found."""
    if name in BUILTIN_PRESETS:
        return BUILTIN_PRESETS[name]
    return _load_user_presets().get(name)


def add_user_preset(name: str, description: str, mode: str, system_hint: str) -> None:
    presets = _load_user_presets()
    presets[name] = {"description": description, "mode": mode, "system_hint": system_hint}
    _save_user_presets(presets)


def delete_user_preset(name: str) -> bool:
    if name in BUILTIN_PRESETS:
        raise ValueError(f"Cannot delete built-in preset '{name}'")
    presets = _load_user_presets()
    if name not in presets:
        return False
    del presets[name]
    _save_user_presets(presets)
    return True
