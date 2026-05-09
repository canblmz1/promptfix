"""Output guard: validate and clean provider output."""

from __future__ import annotations

from dataclasses import dataclass, field

from promptfix.intent import Intent


@dataclass
class GuardResult:
    valid: bool
    output: str
    reasons: list[str] = field(default_factory=list)


FORBIDDEN_STARTS = [
    "here is", "here's", "sure,", "certainly,", "project:",
    "current context", "daemon started", "promptfix", "files read",
    "cache:", "i'll help", "let me", "of course",
]

BROADENING_WORDS = ["refactor", "rewrite", "overhaul", "redesign", "restructure"]

MINIMAL_PHRASES = [
    "minimal", "targeted", "avoid unrelated", "small", "scoped",
    "keep the change", "do not refactor", "don't refactor",
]

FALLBACKS = {
    "bugfix": (
        "Investigate and fix {topic} with minimal, targeted changes. "
        "Inspect the relevant existing flow first, avoid unrelated refactors "
        "or config/secrets changes, run relevant tests if available, and "
        "summarize the root cause, fix, and verification steps."
    ),
    "feature": (
        "Implement {topic} following existing project conventions. "
        "Keep the change scoped, avoid unrelated refactors, add or update "
        "relevant tests if appropriate, and summarize the implementation "
        "and verification steps."
    ),
    "performance": (
        "Investigate and improve {topic} performance with minimal, targeted changes. "
        "Identify the likely bottleneck, avoid unrelated refactors, run relevant "
        "tests or benchmarks if available, and summarize the changes and "
        "verification steps."
    ),
    "review": (
        "Review {topic} and identify the highest-confidence issue or improvement. "
        "Do not make broad changes unless clearly necessary. Report findings first, "
        "then make only minimal safe changes if appropriate."
    ),
    "unknown": (
        "Investigate {topic} and make minimal, safe improvements. "
        "Avoid unrelated refactors or config changes, run relevant tests "
        "if available, and summarize what was done and why."
    ),
}


def clean_output(text: str) -> str:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()
    if text.startswith("`") and text.endswith("`") and text.count("`") == 2:
        text = text[1:-1].strip()
    for prefix in ["Here is the rewritten prompt:", "Here is your optimized prompt:",
                   "Here's the rewritten prompt:", "Sure,", "Certainly,"]:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()
    return text


def validate_output(output: str, intent: Intent) -> GuardResult:
    reasons: list[str] = []
    cleaned = clean_output(output)

    if not cleaned:
        return GuardResult(valid=False, output="", reasons=["empty output"])

    lowered = cleaned.lower()
    first_line = lowered.split("\n")[0].strip()

    for phrase in FORBIDDEN_STARTS:
        if first_line.startswith(phrase):
            reasons.append(f"starts with forbidden phrase: {phrase}")
            break

    if not intent.allow_refactor:
        for word in BROADENING_WORDS:
            if word in lowered:
                reasons.append(f"contains broadening word '{word}' when refactor not allowed")
                break

    if "minimal_changes" in intent.constraints:
        if not any(p in lowered for p in MINIMAL_PHRASES):
            reasons.append("missing minimal/targeted language for minimal_changes constraint")

    if intent.keywords:
        has_keyword = any(kw.lower() in lowered for kw in intent.keywords[:5])
        has_related = any(
            w in lowered for w in _topic_words(intent)
        )
        if not has_keyword and not has_related:
            reasons.append("output does not mention any intent keywords")

    summary_indicators = ["project overview", "codebase analysis", "architecture review"]
    if any(ind in lowered for ind in summary_indicators):
        reasons.append("output looks like a repo summary")

    return GuardResult(valid=len(reasons) == 0, output=cleaned, reasons=reasons)


def get_fallback(intent: Intent) -> str:
    topic = _extract_topic(intent)
    template = FALLBACKS.get(intent.task_type, FALLBACKS["unknown"])
    # Use str.replace instead of str.format to avoid KeyError if topic contains
    # brace characters from user input (e.g. "{something}").
    return template.replace("{topic}", topic)


def _extract_topic(intent: Intent) -> str:
    domain_words = []
    if intent.domain != "unknown":
        domain_words.append(intent.domain)
    keywords = [kw for kw in intent.keywords if kw not in BROADENING_WORDS][:3]
    if keywords:
        domain_words.extend(keywords)
    if domain_words:
        return " ".join(domain_words[:3])
    words = intent.normalized_text.split()[:5]
    return " ".join(words) if words else "the issue"


def _topic_words(intent: Intent) -> list[str]:
    words = []
    if intent.domain != "unknown":
        words.append(intent.domain)
    words.extend(intent.normalized_text.lower().split()[:5])
    return [w for w in words if len(w) > 3]
