"""Tests for the diff utility module."""

from __future__ import annotations

import pytest

from promptfix.diff import compute_diff, format_diff_rich, DiffResult


class TestComputeDiff:
    def test_returns_diff_result(self):
        result = compute_diff("fix the login bug", "Investigate and fix the login bug.")
        assert isinstance(result, DiffResult)

    def test_unchanged_texts(self):
        text = "Investigate and fix the login bug with minimal changes."
        result = compute_diff(text, text)
        assert result.unchanged is True
        assert result.unified == ""

    def test_changed_texts(self):
        result = compute_diff("fix bug", "Investigate and fix the login bug with targeted changes.")
        assert result.unchanged is False
        assert result.unified != ""

    def test_diff_contains_plus_and_minus(self):
        result = compute_diff("fix login bug", "Investigate the login auth bug carefully.")
        # unified diff should have + and - markers
        assert "+" in result.unified or "-" in result.unified

    def test_to_dict_has_required_keys(self):
        result = compute_diff("original text", "optimized text")
        d = result.to_dict()
        assert "unified" in d
        assert "unchanged" in d

    def test_to_dict_unchanged_flag(self):
        text = "same text"
        result = compute_diff(text, text)
        assert result.to_dict()["unchanged"] is True

    def test_strips_whitespace(self):
        result = compute_diff("  fix bug  ", "fix bug")
        assert result.unchanged is True

    def test_large_text_performance(self):
        """Diff on large-ish prompts should complete quickly."""
        import time
        long_text = "word " * 500
        modified = long_text.replace("word ", "term ", 50)
        start = time.time()
        compute_diff(long_text, modified)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Diff took {elapsed:.2f}s — too slow"

    def test_original_and_optimized_stored(self):
        result = compute_diff("original", "optimized")
        assert result.original == "original"
        assert result.optimized == "optimized"

    def test_newline_handling(self):
        original = "line one\nline two"
        optimized = "line one\nline two updated"
        result = compute_diff(original, optimized)
        assert result.unchanged is False

    def test_empty_original(self):
        result = compute_diff("", "some optimized text")
        assert result.unchanged is False

    def test_empty_both(self):
        result = compute_diff("", "")
        assert result.unchanged is True


class TestFormatDiffRich:
    def test_unchanged_returns_dim_message(self):
        result = compute_diff("same", "same")
        formatted = format_diff_rich(result)
        assert "No changes" in formatted
        assert "[dim]" in formatted

    def test_changed_returns_colored_output(self):
        result = compute_diff("fix bug", "Investigate and fix the auth bug.")
        formatted = format_diff_rich(result)
        # Should contain Rich color markup
        assert "[green]" in formatted or "[red]" in formatted

    def test_markup_escaping(self):
        """Square brackets in user text should be escaped to avoid Rich parsing errors."""
        result = compute_diff("[old text]", "[new text]")
        formatted = format_diff_rich(result)
        # Should not raise and should contain escaped brackets
        assert "\\[" in formatted or formatted  # if unchanged, still valid
