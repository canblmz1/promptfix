"""Prompt quality scorer — heuristic scoring without an LLM call.

Scores the rewritten output on 5 dimensions (0-20 each, total 0-100):
  - specificity: concrete action words vs. vague filler
  - conciseness: appropriate length for mode
  - actionability: clear deliverable or instruction present
  - safety: no broadening words or forbidden prefixes
  - intent_alignment: output reflects detected task type / domain

Usage:
    from promptfix.scorer import score_output
    result = score_output(text, intent, mode)
    print(result.total)          # 0-100
    print(result.grade)          # A / B / C / D / F
    print(result.breakdown)      # dict of dimension -> score
    print(result.suggestions)    # list of improvement hints
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from promptfix.intent import Intent

# ---------------------------------------------------------------------------
# Word lists
# ---------------------------------------------------------------------------

_ACTION_WORDS = {
    "investigate", "inspect", "identify", "fix", "implement", "add", "create",
    "refactor", "optimize", "review", "test", "verify", "validate", "ensure",
    "debug", "trace", "reproduce", "check", "update", "remove", "replace",
    "incele", "düzelt", "ekle", "oluştur", "test et", "doğrula", "kontrol et",
    "araştır", "tespit et", "uygula",
}

_VAGUE_WORDS = {
    "stuff", "things", "something", "somehow", "maybe", "perhaps",
    "probably", "kind of", "sort of", "etc", "and so on", "various",
    "şeyler", "falan", "filan", "belki", "bir şekilde", "vs",
}

_BROADENING_WORDS = {
    "refactor", "rewrite", "overhaul", "redesign", "restructure",
    "clean up everything", "completely", "from scratch",
}

_FORBIDDEN_STARTS = (
    "here is", "here's", "sure,", "certainly,", "of course",
    "let me", "i'll help", "i will", "project:", "promptfix",
    "current context",
)

_DELIVERABLE_SIGNALS = [
    r"\bdeliver\b", r"\bsummariz", r"\bprovide\b", r"\boutput\b",
    r"\breturn\b", r"\bverif", r"\btest\b", r"\bensure\b",
    r"\bvalidat", r"\bresult\b", r"\bconfirm\b",
]

_MODE_IDEAL_LENGTHS = {
    "fast": (20, 80),
    "short": (50, 180),
    "raw": (30, 150),
    "agent": (100, 500),
    "explain": (100, 400),
}

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScoreResult:
    total: int                              # 0-100
    breakdown: dict[str, int] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)

    @property
    def grade(self) -> str:
        if self.total >= 85:
            return "A"
        if self.total >= 70:
            return "B"
        if self.total >= 55:
            return "C"
        if self.total >= 40:
            return "D"
        return "F"

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "grade": self.grade,
            "breakdown": self.breakdown,
            "suggestions": self.suggestions,
        }

# ---------------------------------------------------------------------------
# Dimension scorers (each returns 0-20)
# ---------------------------------------------------------------------------

def _score_specificity(text: str) -> tuple[int, list[str]]:
    """Reward concrete action words, penalize vague language."""
    words = set(text.lower().split())
    action_hits = len(words & _ACTION_WORDS)
    vague_hits = len(words & _VAGUE_WORDS)

    score = min(20, action_hits * 4)
    score = max(0, score - vague_hits * 3)

    hints = []
    if action_hits == 0:
        hints.append("Add a concrete action verb (investigate, fix, implement, verify…)")
    if vague_hits > 0:
        hints.append(f"Remove vague filler words ({', '.join(words & _VAGUE_WORDS)})")
    return score, hints


def _score_conciseness(text: str, mode: str) -> tuple[int, list[str]]:
    """Score based on word count relative to ideal range for the mode."""
    word_count = len(text.split())
    lo, hi = _MODE_IDEAL_LENGTHS.get(mode, (50, 180))
    hints = []

    if lo <= word_count <= hi:
        score = 20
    elif word_count < lo:
        ratio = word_count / lo
        score = int(20 * ratio)
        hints.append(f"Output is very short ({word_count} words). Add more context or instructions.")
    else:  # too long
        overshoot = word_count - hi
        penalty = min(15, overshoot // 10)
        score = max(5, 20 - penalty)
        hints.append(f"Output is long ({word_count} words). Tighten for {mode} mode (ideal: {lo}-{hi}).")

    return score, hints


def _score_actionability(text: str) -> tuple[int, list[str]]:
    """Check for deliverable/verification signals."""
    lowered = text.lower()
    hits = sum(1 for pat in _DELIVERABLE_SIGNALS if re.search(pat, lowered))
    score = min(20, hits * 5)
    hints = []
    if score < 10:
        hints.append("Include a verification or deliverable step (e.g., 'verify with tests', 'return summary').")
    return score, hints


def _score_safety(text: str) -> tuple[int, list[str]]:
    """Penalize broadening words and forbidden starts."""
    lowered = text.lower().strip()
    hints = []
    score = 20

    # Forbidden prefix
    for prefix in _FORBIDDEN_STARTS:
        if lowered.startswith(prefix):
            score -= 10
            hints.append(f"Remove conversational opener (starts with '{prefix}').")
            break

    # Broadening words (only penalize when not explicitly requested)
    broad_found = {w for w in _BROADENING_WORDS if w in lowered}
    if broad_found:
        score -= min(10, len(broad_found) * 4)
        hints.append(
            f"Broadening words found ({', '.join(broad_found)}). "
            "Use only if the original text explicitly requested a full rewrite."
        )

    return max(0, score), hints


def _score_intent_alignment(text: str, intent: Intent) -> tuple[int, list[str]]:
    """Check that the output reflects the detected task type and domain."""
    lowered = text.lower()
    hints = []
    score = 20

    # Task type signals
    task_signals = {
        "bugfix": ["fix", "investigate", "root cause", "reproduce", "patch", "düzelt"],
        "performance": ["bottleneck", "optimize", "profile", "latency", "benchmark"],
        "feature": ["implement", "add", "create", "build"],
        "review": ["review", "inspect", "identify", "check", "assess"],
        "refactor": ["refactor", "restructure", "clean", "organize"],
        "test": ["test", "coverage", "assert", "spec", "verify"],
        "security": ["secure", "vulnerability", "sanitize", "validate", "xss", "csrf", "injection"],
        "deploy": ["deploy", "release", "rollback", "pipeline", "migration"],
    }
    if intent.task_type != "unknown":
        signals = task_signals.get(intent.task_type, [])
        if signals and not any(s in lowered for s in signals):
            score -= 8
            hints.append(
                f"Output doesn't reflect task type '{intent.task_type}'. "
                f"Include keywords like: {', '.join(signals[:3])}."
            )

    # Domain signals
    domain_signals = {
        "auth": ["login", "token", "auth", "session", "jwt"],
        "database": ["query", "schema", "migration", "db", "sql"],
        "api": ["endpoint", "route", "request", "response"],
        "security": ["security", "vulnerability", "sanitize"],
        "deploy": ["deploy", "release", "prod"],
    }
    if intent.domain in domain_signals:
        signals = domain_signals[intent.domain]
        if not any(s in lowered for s in signals):
            score -= 5
            hints.append(f"Consider mentioning the '{intent.domain}' domain context.")

    return max(0, score), hints

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_output(text: str, intent: Intent, mode: str) -> ScoreResult:
    """Score a rewritten prompt heuristically. Returns ScoreResult (0-100)."""
    all_hints: list[str] = []
    breakdown: dict[str, int] = {}

    s1, h1 = _score_specificity(text)
    s2, h2 = _score_conciseness(text, mode)
    s3, h3 = _score_actionability(text)
    s4, h4 = _score_safety(text)
    s5, h5 = _score_intent_alignment(text, intent)

    breakdown["specificity"] = s1
    breakdown["conciseness"] = s2
    breakdown["actionability"] = s3
    breakdown["safety"] = s4
    breakdown["intent_alignment"] = s5

    all_hints = h1 + h2 + h3 + h4 + h5

    total = s1 + s2 + s3 + s4 + s5

    return ScoreResult(total=total, breakdown=breakdown, suggestions=all_hints)
