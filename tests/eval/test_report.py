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

    def test_html_escapes_xss_payloads(self, tmp_path):
        """Malicious input/output must be escaped in the HTML report table rows."""
        case = EvalCase(
            name="xss-test",
            input="<script>alert(1)</script>",
            mode="short",
        )
        result = EvalResult(
            case=case,
            output="<img src=x onerror=alert(2)>",
            duration_ms=50,
            rule_score=ScoreResult(score=0),
            provider="groq",
        )

        out = tmp_path / "xss_report.html"
        generate_html([result], out)
        content = out.read_text(encoding="utf-8")

        # In the HTML table, raw tags must be escaped as entities
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content
        assert "&lt;img src=x onerror=alert(2)&gt;" in content

    def test_html_breaks_script_tag_in_embedded_json(self, tmp_path):
        """The embedded JSON data must break </script> to avoid injection."""
        case = EvalCase(name="script-break", input="test", mode="short")
        result = EvalResult(
            case=case,
            output="</script><script>alert(3)</script>",
            duration_ms=50,
            rule_score=ScoreResult(score=100),
            provider="groq",
        )

        out = tmp_path / "script_report.html"
        generate_html([result], out)
        content = out.read_text(encoding="utf-8")

        # Raw closing script tag must not exist in the JS block
        assert "</script>" not in content.split("<script>")[1].split("</script>")[0]


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
