"""Scoring engine: rule-based and LLM-based."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from promptfix.intent import parse_intent


@dataclass
class ScoreResult:
    score: int  # 0-100
    breakdown: list[str] = field(default_factory=list)


def run_assertions(output: str, asserts: list[dict[str, Any]], input_text: str) -> ScoreResult:
    """Run rule-based assertions and return a score."""
    if not asserts:
        return ScoreResult(score=100, breakdown=["no assertions to check"])

    breakdown: list[str] = []
    passed = 0

    for assertion in asserts:
        ok, msg = _check_assertion(output, assertion, input_text)
        if ok:
            passed += 1
            breakdown.append(f"[OK] {assertion.get('type')}")
        else:
            breakdown.append(f"[FAIL] {assertion.get('type')}: {msg}")

    score = int((passed / len(asserts)) * 100)
    return ScoreResult(score=score, breakdown=breakdown)


def _check_assertion(output: str, assertion: dict[str, Any], input_text: str) -> tuple[bool, str]:
    atype = assertion.get("type", "")
    output_lower = output.lower()

    if atype == "contains":
        values = assertion.get("value", [])
        if isinstance(values, str):
            values = [values]
        missing = [v for v in values if v.lower() not in output_lower]
        if missing:
            return False, f"missing: {', '.join(missing)}"
        return True, ""

    elif atype == "not_contains":
        values = assertion.get("value", [])
        if isinstance(values, str):
            values = [values]
        found = [v for v in values if v.lower() in output_lower]
        if found:
            return False, f"found forbidden: {', '.join(found)}"
        return True, ""

    elif atype == "intent_match":
        intent = parse_intent(input_text)
        expected_task = assertion.get("task_type")
        expected_domain = assertion.get("domain")
        if expected_task and intent.task_type != expected_task:
            return False, f"task_type: expected {expected_task}, got {intent.task_type}"
        if expected_domain and intent.domain != expected_domain:
            return False, f"domain: expected {expected_domain}, got {intent.domain}"
        return True, ""

    elif atype == "length_limit":
        mode = assertion.get("mode", "short")
        word_count = len(output.split())
        limits = {"fast": 60, "short": 120, "agent": 300, "explain": 300, "raw": 200}
        limit = limits.get(mode, 120)
        if word_count > limit:
            return False, f"word count {word_count} > limit {limit}"
        return True, ""

    elif atype == "no_fences":
        if "```" in output or (output.startswith("`") and output.endswith("`")):
            return False, "contains markdown fences"
        return True, ""

    elif atype == "no_prefixes":
        prefixes = ["here is", "here's", "sure,", "certainly,", "promptfix"]
        first_line = output_lower.split("\n")[0].strip()
        for p in prefixes:
            if first_line.startswith(p):
                return False, f"starts with '{p}'"
        return True, ""

    elif atype == "not_empty":
        if not output.strip() or output.startswith("ERROR:"):
            return False, "empty or error output"
        return True, ""

    return True, f"unknown assertion type: {atype}"


def run_llm_judge(
    output: str,
    input_text: str,
    mode: str,
    provider,
) -> ScoreResult:
    """Use the LLM provider itself as a judge."""
    judge_prompt = (
        "You are a prompt quality evaluator. Score the following rewritten prompt "
        "on a scale of 0-100 based on these criteria (each 0-20):\n"
        "1. Clarity: Is it clear and unambiguous?\n"
        "2. Specificity: Does it include concrete technical details?\n"
        "3. Actionability: Can an AI coding agent act on it immediately?\n"
        "4. Constraint Adherence: Does it respect the user's constraints (e.g., minimal changes)?\n"
        "5. Intent Alignment: Does it match the original request without broadening?\n\n"
        f"Original request: {input_text}\n"
        f"Rewritten prompt ({mode} mode): {output}\n\n"
        "Respond with ONLY a JSON object: {\"score\": <int>, \"reason\": \"<brief reason>\"}"
    )

    messages = [
        {"role": "system", "content": "You are a strict prompt quality evaluator."},
        {"role": "user", "content": judge_prompt},
    ]

    raw = provider.complete(messages, temperature=0.0)
    score, reason = _parse_judge_response(raw)
    return ScoreResult(score=score, breakdown=[f"LLM judge: {reason}"])


def _parse_judge_response(text: str) -> tuple[int, str]:
    """Extract score from LLM judge response."""
    import json
    import re

    text = text.strip()
    # Try to find JSON
    match = re.search(r'\{[^}]*"score"[^}]*\}', text)
    if match:
        try:
            data = json.loads(match.group())
            score = int(data.get("score", 0))
            reason = data.get("reason", "no reason")
            return max(0, min(100, score)), reason
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: search for a number 0-100
    nums = re.findall(r'\b(\d{1,3})\b', text)
    for n in nums:
        val = int(n)
        if 0 <= val <= 100:
            return val, text[:100]

    return 50, "could not parse judge response"
