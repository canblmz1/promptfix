"""Prompt rewrite templates for each mode."""

from __future__ import annotations

from promptfix.intent import Intent

SYSTEM_PROMPT = """\
You are PromptFix, a coding-agent prompt rewriter.

Rewrite the selected text into a clearer, shorter, more useful prompt for another AI coding agent.

Rules:
- The selected text is the source of truth.
- Do not broaden the task.
- Do not summarize unrelated context.
- Do not say "refactor", "rewrite", "overhaul", or "redesign" unless the selected text explicitly asks for it.
- If the task is a bugfix, prefer inspect -> root cause -> minimal fix -> validation.
- If the user asks to avoid breaking things, include minimal targeted changes and avoid unrelated changes.
- Protect secrets, credentials, and production config.
- Return only the optimized prompt.
- Do not prefix with "Here is" or wrap the result in quotes.
- Do not use markdown code fences.
- Turkish casual words (kral, knk, kanka, aga, reis, hocam) are greetings, not technical terms. Ignore them."""


MODE_INSTRUCTIONS = {
    "fast": "Ultra-compact, max 60 words. Core ask only. No guardrails unless critical.",
    "short": "One compact paragraph, max 120 words. Include coding guardrails.",
    "agent": """\
Structured output format:
Task:
...
Context:
...
Instructions:
- ...
Constraints:
- ...
Validation:
- ...
Deliverables:
- ...""",
    "raw": "Rewrite only. No extra structure. One clean paragraph.",
    "explain": "Rewrite with reasoning: include root-cause thinking, steps, and verification. Max 300 words.",
}


def build_rewrite_prompt(
    selected_text: str,
    intent: Intent,
    context_lite: str,
    mode: str,
    preset_hint: str = "",
) -> list[dict[str, str]]:
    """Build the messages array sent to the provider."""
    user_parts = [
        f"Selected text:\n<<<\n{selected_text}\n>>>",
        "",
        "Detected intent:",
        "<<<",
        f"type: {intent.task_type}",
        f"domain: {intent.domain}",
        f"constraints: {', '.join(intent.constraints) if intent.constraints else 'none'}",
        f"allow_refactor: {intent.allow_refactor}",
        ">>>",
    ]

    if preset_hint:
        user_parts.append(f"\nPreset instructions:\n<<<\n{preset_hint}\n>>>")

    if context_lite and mode != "raw":
        user_parts.append(f"\nOptional repo hints:\n<<<\n{context_lite}\n>>>")

    mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["short"])
    user_parts.append(f"\nMode: {mode}\n{mode_instruction}")

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def build_retry_prompt(selected_text: str) -> list[dict[str, str]]:
    """Stricter retry prompt with no context."""
    return [
        {
            "role": "system",
            "content": (
                "You are a coding prompt rewriter. "
                "Return only the improved prompt. No explanation. No quotes. No fences."
            ),
        },
        {
            "role": "user",
            "content": (
                "Rewrite ONLY the selected text into a coding-agent prompt. "
                "Ignore all repo context. Return only the improved prompt.\n\n"
                f"Selected text:\n<<<\n{selected_text}\n>>>"
            ),
        },
    ]
