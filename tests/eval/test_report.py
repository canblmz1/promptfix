"""Tests for eval report generation."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from promptfix.eval.report import generate_html, print_table
from promptfix.eval.runner import EvalCase, EvalResult
from promptfix.eval.scorer import ScoreResult


class TestGenerateHTML:
    def test_html_report_created(self, tmp_path):
        case = EvalCase(name="test1", input="hello", mode="short")
        result = EvalResult(
            case=case,
            output="optimized",
            duration_ms=100,
            rule_score=ScoreResult(score=90),
            provider="groq",
        )

        out = tmp_path / "report.html"
        generate_html([result], out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "test1" in content
        assert "90/100" in content
        assert "groq" in content

    def test_html_with_llm_score(self, tmp_path):
        case = EvalCase(name="test2", input="world", mode="agent")
        result = EvalResult(
            case=case,
            output="out",
            duration_ms=200,
            rule_score=ScoreResult(score=80),
            llm_score=ScoreResult(score=90, breakdown=["good"]),
            provider="ollama",
        )

        out = tmp_path / "report2.html"
        generate_html([result], out)
        content = out.read_text(encoding="utf-8")
        assert "test2" in content
        assert "ollama" in content


class TestPrintTable:
    def test_table_output(self, capsys):
        from rich.console import Console
        console = Console(force_terminal=True, width=120)

        case = EvalCase(name="t1", input="in", mode="short")
        result = EvalResult(
            case=case,
            output="out",
            duration_ms=50,
            rule_score=ScoreResult(score=95),
            provider="groq",
        )

        print_table([result], console)
        # Rich output goes to console file, not easily captured.
        # Just verify it doesn't crash.
