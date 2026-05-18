"""Tests for the eval engine."""

from unittest.mock import MagicMock

import pytest
import yaml

from promptfix.eval.runner import EvalCase, load_suite, run_eval
from promptfix.eval.scorer import _parse_judge_response, run_assertions, run_llm_judge


class TestLoadSuite:
    def test_load_single_file(self, tmp_path):
        data = {
            "tests": [
                {"name": "test1", "input": "hello", "mode": "short"},
                {"name": "test2", "input": "world", "mode": "agent"},
            ]
        }
        f = tmp_path / "suite.yaml"
        f.write_text(yaml.dump(data), encoding="utf-8")

        cases = load_suite(f)
        assert len(cases) == 2
        assert cases[0].name == "test1"
        assert cases[0].input == "hello"
        assert cases[0].mode == "short"

    def test_load_directory(self, tmp_path):
        for i in range(3):
            data = {"tests": [{"name": f"t{i}", "input": f"in{i}", "mode": "short"}]}
            (tmp_path / f"suite{i}.yaml").write_text(yaml.dump(data), encoding="utf-8")

        cases = load_suite(tmp_path)
        assert len(cases) == 3

    def test_empty_suite(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text(yaml.dump({"tests": []}), encoding="utf-8")
        cases = load_suite(f)
        assert cases == []

    def test_invalid_yaml_raises_runtime_error(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("this is: [not: valid yaml: :::", encoding="utf-8")
        with pytest.raises(RuntimeError, match="Invalid YAML"):
            load_suite(bad)


class TestRunEval:
    def test_eval_with_mock_provider(self):
        mock = MagicMock()
        mock.complete.return_value = (
            "Investigate and fix the login token refresh issue "
            "with minimal, targeted changes. Inspect the auth flow first."
        )

        cases = [
            EvalCase(
                name="auth bugfix",
                input="login token refresh bozuldu başka yeri bozma",
                mode="short",
                asserts=[
                    {"type": "contains", "value": ["minimal", "auth"]},
                    {"type": "not_contains", "value": ["refactor"]},
                    {"type": "intent_match", "task_type": "bugfix", "domain": "auth"},
                ],
            )
        ]

        config = {
            "provider": "groq",
            "default_mode": "short",
            "validation": {"enabled": False},
            "providers": {"groq": {"model": "test"}},
        }

        results = run_eval(cases, provider=mock, config=config)
        assert len(results) == 1
        assert results[0].case.name == "auth bugfix"
        assert results[0].rule_score.score > 0
        assert "auth" in results[0].output.lower() or "login" in results[0].output.lower()

    def test_eval_error_handling(self):
        mock = MagicMock()
        mock.complete.side_effect = RuntimeError("provider down")

        cases = [EvalCase(name="fail", input="test", mode="short")]
        config = {"provider": "groq", "validation": {"enabled": False}, "providers": {"groq": {"model": "t"}}}

        results = run_eval(cases, provider=mock, config=config)
        assert len(results) == 1
        assert results[0].output.startswith("ERROR:")

    def test_eval_llm_judge(self):
        mock = MagicMock()
        mock.complete.side_effect = [
            "Fix the login bug with minimal changes.",
            '{"score": 90, "reason": "good prompt"}',
        ]

        cases = [EvalCase(name="judge test", input="login bug", mode="short", asserts=[])]
        config = {"provider": "groq", "validation": {"enabled": False}, "providers": {"groq": {"model": "t"}}}

        results = run_eval(cases, provider=mock, config=config, use_llm_judge=True)
        assert results[0].llm_score is not None
        assert results[0].llm_score.score == 90


class TestScorer:
    def test_contains_pass(self):
        r = run_assertions("fix the auth bug", [{"type": "contains", "value": ["auth", "bug"]}], "input")
        assert r.score == 100

    def test_contains_fail(self):
        r = run_assertions("fix the auth bug", [{"type": "contains", "value": ["payment"]}], "input")
        assert r.score == 0

    def test_not_contains_pass(self):
        r = run_assertions("fix the bug", [{"type": "not_contains", "value": ["refactor"]}], "input")
        assert r.score == 100

    def test_not_contains_fail(self):
        r = run_assertions("refactor the code", [{"type": "not_contains", "value": ["refactor"]}], "input")
        assert r.score == 0

    def test_intent_match(self):
        r = run_assertions(
            "output",
            [{"type": "intent_match", "task_type": "bugfix", "domain": "auth"}],
            "login token refresh bozuldu"
        )
        assert r.score == 100

    def test_no_fences(self):
        r = run_assertions("clean text", [{"type": "no_fences"}], "input")
        assert r.score == 100

        r2 = run_assertions("```code```", [{"type": "no_fences"}], "input")
        assert r2.score == 0

    def test_no_prefixes(self):
        r = run_assertions("Here is the fix", [{"type": "no_prefixes"}], "input")
        assert r.score == 0

    def test_not_empty(self):
        r = run_assertions("", [{"type": "not_empty"}], "input")
        assert r.score == 0

    def test_multiple_assertions(self):
        r = run_assertions(
            "fix the auth bug with minimal changes",
            [
                {"type": "contains", "value": ["auth"]},
                {"type": "not_contains", "value": ["refactor"]},
                {"type": "not_empty"},
            ],
            "input"
        )
        assert r.score == 100

    def test_parse_judge_response_json(self):
        score, reason = _parse_judge_response('{"score": 85, "reason": "great"}')
        assert score == 85
        assert reason == "great"

    def test_parse_judge_response_number_only(self):
        score, reason = _parse_judge_response("The score is 78 out of 100.")
        assert score == 78

    def test_parse_judge_response_fallback(self):
        score, reason = _parse_judge_response("no idea")
        assert score == 50

    def test_run_llm_judge(self):
        mock = MagicMock()
        mock.complete.return_value = '{"score": 92, "reason": "excellent"}'

        r = run_llm_judge("fix the bug", "bug report", "short", mock)
        assert r.score == 92
        assert "excellent" in r.breakdown[0]
