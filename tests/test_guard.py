"""Tests for the output guard."""

import pytest

from promptfix.guard import clean_output, get_fallback, validate_output
from promptfix.intent import parse_intent


class TestCleanOutput:
    def test_removes_here_is(self):
        text = "Here is the rewritten prompt: Fix the login bug."
        assert clean_output(text) == "Fix the login bug."

    def test_removes_heres(self):
        text = "Here's the rewritten prompt: Fix the login bug."
        assert clean_output(text) == "Fix the login bug."

    def test_removes_code_fences(self):
        text = "```\nFix the login bug.\n```"
        assert clean_output(text) == "Fix the login bug."

    def test_removes_code_fences_with_language(self):
        text = "```text\nFix the login bug.\n```"
        assert clean_output(text) == "Fix the login bug."

    def test_removes_surrounding_quotes(self):
        text = '"Fix the login bug."'
        assert clean_output(text) == "Fix the login bug."

    def test_removes_certainly(self):
        text = "Certainly, here is the prompt: Fix it."
        assert clean_output(text) == "here is the prompt: Fix it."

    def test_removes_sure(self):
        text = "Sure, here you go: Fix the bug."
        assert clean_output(text) == "here you go: Fix the bug."

    def test_leaves_clean_output(self):
        text = "Investigate and fix the auth token refresh issue."
        assert clean_output(text) == text

    def test_handles_empty(self):
        assert clean_output("") == ""

    def test_handles_whitespace_only(self):
        assert clean_output("   \n   ") == ""


class TestValidation:
    def test_valid_bugfix_output(self):
        intent = parse_intent("login token refresh bozuldu başka yeri bozma")
        output = "Investigate and fix the login token refresh issue with minimal, targeted changes."
        result = validate_output(output, intent)
        assert result.valid is True

    def test_rejects_forbidden_start_here_is(self):
        intent = parse_intent("login bozuldu")
        output = "Here is your optimized prompt for fixing the login."
        result = validate_output(output, intent)
        assert result.valid is False
        assert any("forbidden" in r for r in result.reasons)

    def test_rejects_forbidden_start_project(self):
        intent = parse_intent("fix the login")
        output = "Project: MyApp is a React application that..."
        result = validate_output(output, intent)
        assert result.valid is False

    def test_rejects_forbidden_start_promptfix(self):
        intent = parse_intent("fix the login")
        output = "PromptFix has analyzed your request and..."
        result = validate_output(output, intent)
        assert result.valid is False

    def test_rejects_broadening_when_not_allowed(self):
        intent = parse_intent("fix login bug başka yeri bozma")
        output = "Refactor the entire authentication system to fix login issues."
        result = validate_output(output, intent)
        assert result.valid is False

    def test_allows_refactor_when_requested(self):
        intent = parse_intent("refactor the auth module")
        output = "Refactor the auth module to improve readability."
        result = validate_output(output, intent)
        assert result.valid is True

    def test_rejects_project_summary(self):
        intent = parse_intent("fix login token")
        output = "Project overview: this codebase uses React and Node."
        result = validate_output(output, intent)
        assert result.valid is False

    def test_rejects_codebase_analysis(self):
        intent = parse_intent("fix login")
        output = "Codebase analysis: the project has 50 files across 3 modules."
        result = validate_output(output, intent)
        assert result.valid is False

    def test_requires_minimal_language(self):
        intent = parse_intent("login bozuldu başka yeri bozma")
        output = "Fix the login token issue completely and thoroughly."
        result = validate_output(output, intent)
        assert result.valid is False
        assert any("minimal" in r for r in result.reasons)

    def test_rejects_empty(self):
        intent = parse_intent("fix login")
        result = validate_output("", intent)
        assert result.valid is False

    def test_rejects_no_keywords(self):
        intent = parse_intent("login token refresh bozuldu")
        output = "Make some improvements to the system performance."
        result = validate_output(output, intent)
        assert result.valid is False
        assert any("keyword" in r for r in result.reasons)

    def test_valid_with_domain_word(self):
        """Output that mentions the domain (auth) should pass even if
        it doesn't repeat every keyword verbatim."""
        intent = parse_intent("login token refresh bozuldu")
        output = "Fix the auth token refresh flow. Inspect the session handling first."
        result = validate_output(output, intent)
        assert result.valid is True


class TestFallback:
    def test_bugfix_fallback(self):
        intent = parse_intent("login token refresh bozuldu")
        fallback = get_fallback(intent)
        assert "Investigate and fix" in fallback
        assert "auth" in fallback or "login" in fallback or "token" in fallback

    def test_feature_fallback(self):
        intent = parse_intent("implement new dashboard widget")
        fallback = get_fallback(intent)
        assert "Implement" in fallback

    def test_performance_fallback(self):
        intent = parse_intent("dashboard yavaş render")
        fallback = get_fallback(intent)
        assert "performance" in fallback

    def test_review_fallback(self):
        intent = parse_intent("projeyi incele küçük iyileştirme")
        fallback = get_fallback(intent)
        assert "Review" in fallback

    def test_unknown_fallback(self):
        intent = parse_intent("do something with the code")
        fallback = get_fallback(intent)
        assert "Investigate" in fallback

    def test_fallback_topic_with_braces_does_not_raise(self):
        """Topic containing brace characters from user input must not raise KeyError."""
        intent = parse_intent("fix {unknown_key} in the auth module")
        fallback = get_fallback(intent)
        assert isinstance(fallback, str)
        assert len(fallback) > 0

    def test_fallback_topic_with_format_spec_does_not_raise(self):
        """Topic with Python format-spec-like content must not raise."""
        intent = parse_intent("fix {0!r} edge case başka yeri bozma")
        fallback = get_fallback(intent)
        assert isinstance(fallback, str)
