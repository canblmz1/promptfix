"""Intent extraction: parse selected text into structured intent."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Intent:
    original_text: str
    normalized_text: str
    task_type: str = "unknown"
    domain: str = "unknown"
    keywords: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    allow_refactor: bool = True
    needs_context: bool = False


TASK_KEYWORDS = {
    "bugfix": [
        "bozuldu", "çalışmıyor", "patlıyor", "hata", "bug", "broken",
        "failing", "error", "crash", "fix", "sorun", "problem",
        "500", "404", "401", "403", "dönüyor",
    ],
    "performance": [
        "yavaş", "kasıyor", "slow", "performance", "render", "latency",
        "lag", "timeout", "donma",
    ],
    "review": [
        "incele", "kontrol et", "review", "check", "inspect", "bak",
    ],
    "feature": [
        "ekle", "oluştur", "yap", "implement", "add", "create", "build",
        "yeni", "feature",
    ],
    "test": [
        "test", "spec", "coverage", "test yaz",
    ],
    "docs": [
        "docs", "doküman", "readme", "documentation",
    ],
    "refactor": [
        "refactor", "yeniden düzenle", "refactoring",
    ],
    "cleanup": [
        "temizle", "cleanup", "remove unused", "sil",
    ],
}

DOMAIN_KEYWORDS = {
    "auth": [
        "login", "token", "refresh", "session", "jwt", "auth",
        "oauth", "sso", "logout", "giriş",
    ],
    "payment": [
        "ödeme", "payment", "billing", "invoice", "fatura",
    ],
    "checkout": [
        "checkout", "sepet", "cart", "indirim", "discount", "coupon",
        "kampanya",
    ],
    "dashboard": [
        "dashboard", "panel", "admin",
    ],
    "database": [
        "database", "db", "schema", "migration", "prisma", "drizzle",
        "sql", "query", "veritabanı",
    ],
    "api": [
        "api", "endpoint", "route", "controller", "request", "response",
    ],
    "ui": [
        "ui", "frontend", "component", "css", "page", "render",
    ],
    "cli": [
        "cli", "command", "flag", "terminal",
    ],
    "config": [
        "config", "env", "settings", "ayar",
    ],
    "tests": [
        "test", "spec", "coverage", "jest", "pytest", "vitest",
    ],
}

CONSTRAINT_SIGNALS = {
    "minimal_changes": [
        "başka yeri bozma", "elleme", "abartma", "minimal", "küçük",
        "only", "avoid unrelated", "sadece", "don't break", "bozma",
        "dokunma",
    ],
    "avoid_unrelated_changes": [
        "başka yeri bozma", "elleme", "dokunma", "don't touch",
        "avoid unrelated",
    ],
}

CASUAL_ADDRESS = {
    "kral", "knk", "kanka", "aga", "reis", "hocam", "abi", "usta",
    "şef", "patron", "bro", "dostum", "lan", "ya", "be",
}

PROJECT_LEVEL_SIGNALS = [
    "projeyi incele", "genel bak", "küçük iyileştirme",
    "project review", "small improvement", "improve the project",
    "review this repo",
]


def _normalize(text: str) -> str:
    words = text.split()
    filtered = [w for w in words if w.lower().strip(",.!?") not in CASUAL_ADDRESS]
    return " ".join(filtered)


def _classify_task(text: str) -> str:
    lowered = text.lower()
    for task_type, keywords in TASK_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered:
                return task_type
    return "unknown"


def _classify_domain(text: str) -> str:
    lowered = text.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered:
                return domain
    return "unknown"


def _extract_keywords(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for keywords in DOMAIN_KEYWORDS.values():
        for kw in keywords:
            if kw in lowered and kw not in found:
                found.append(kw)
    for keywords in TASK_KEYWORDS.values():
        for kw in keywords:
            if kw in lowered and kw not in found:
                found.append(kw)
    return found[:8]


def _extract_constraints(text: str) -> list[str]:
    lowered = text.lower()
    constraints = []
    for constraint, signals in CONSTRAINT_SIGNALS.items():
        for sig in signals:
            if sig in lowered:
                if constraint not in constraints:
                    constraints.append(constraint)
                break
    return constraints


def _check_refactor_allowed(text: str, constraints: list[str]) -> bool:
    if "minimal_changes" in constraints or "avoid_unrelated_changes" in constraints:
        lowered = text.lower()
        if "refactor" not in lowered:
            return False
    return True


def _needs_context(text: str, task_type: str) -> bool:
    lowered = text.lower()
    for sig in PROJECT_LEVEL_SIGNALS:
        if sig in lowered:
            return True
    return task_type in ("review", "feature")


def parse_intent(text: str) -> Intent:
    normalized = _normalize(text)
    task_type = _classify_task(text)
    domain = _classify_domain(text)
    keywords = _extract_keywords(text)
    constraints = _extract_constraints(text)
    allow_refactor = _check_refactor_allowed(text, constraints)
    needs_context = _needs_context(text, task_type)

    return Intent(
        original_text=text,
        normalized_text=normalized,
        task_type=task_type,
        domain=domain,
        keywords=keywords,
        constraints=constraints,
        allow_refactor=allow_refactor,
        needs_context=needs_context,
    )
