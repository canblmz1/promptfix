"""ContextLite layer: lightweight project hints without full context dumps."""

from __future__ import annotations

from promptfix.intent import Intent

MODE_CHAR_LIMITS = {
    "raw": 0,
    "fast": 300,
    "short": 600,
    "agent": 1500,
    "explain": 3000,
}

SAFE_RULES = (
    "Keep changes minimal and targeted. "
    "Avoid unrelated refactors. "
    "Do not touch secrets or production config. "
    "Run relevant tests/build if available. "
    "Summarize root cause, fix, and verification steps."
)


def build_context(intent: Intent, mode: str, project_hints: dict | None = None) -> str:
    limit = MODE_CHAR_LIMITS.get(mode, 600)
    if limit == 0:
        return ""

    parts: list[str] = []

    if project_hints:
        if project_hints.get("name"):
            parts.append(f"Project: {project_hints['name']}")
        if project_hints.get("stack"):
            parts.append(f"Stack: {project_hints['stack']}")
        if project_hints.get("test_cmd"):
            parts.append(f"Test: {project_hints['test_cmd']}")
        if project_hints.get("build_cmd"):
            parts.append(f"Build: {project_hints['build_cmd']}")
        if project_hints.get("relevant_paths"):
            paths = project_hints["relevant_paths"]
            if isinstance(paths, list):
                paths = ", ".join(paths[:5])
            parts.append(f"Relevant: {paths}")

    parts.append(f"Rules: {SAFE_RULES}")

    context = "\n".join(parts)
    if len(context) > limit:
        context = context[:limit].rsplit(" ", 1)[0] + "..."
    return context
