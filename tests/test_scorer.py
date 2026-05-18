"""Tests for the prompt quality scorer."""


from promptfix.intent import parse_intent
from promptfix.scorer import ScoreResult, score_output


class TestScoreOutput:
    def _intent(self, text="fix login bug"):
        return parse_intent(text)

    def test_returns_score_result(self):
        intent = self._intent()
        result = score_output("Investigate and fix the login bug with minimal changes.", intent, "short")
        assert isinstance(result, ScoreResult)
        assert 0 <= result.total <= 100

    def test_breakdown_has_five_dimensions(self):
        intent = self._intent()
        result = score_output("Fix the bug.", intent, "short")
        assert set(result.breakdown.keys()) == {
            "specificity", "conciseness", "actionability", "safety", "intent_alignment"
        }
        for val in result.breakdown.values():
            assert 0 <= val <= 20

    def test_grade_a_for_high_score(self):
        intent = self._intent("fix login bug")
        # High quality output
        text = (
            "Investigate and fix the login authentication bug with minimal targeted changes. "
            "Inspect the existing auth flow, identify the root cause, apply a scoped fix, "
            "and verify with relevant tests. Do not refactor unrelated code."
        )
        result = score_output(text, intent, "short")
        assert result.grade in ("A", "B"), f"Expected A or B but got {result.grade} (score={result.total})"

    def test_grade_f_for_low_score(self):
        intent = self._intent()
        # Conversational opener + vague
        result = score_output("Here is a solution to your problem with stuff.", intent, "short")
        assert result.grade in ("F", "D", "C"), f"Expected low grade but got {result.grade}"

    def test_forbidden_start_penalized(self):
        intent = self._intent()
        r_bad = score_output("Here is the fix for the login bug.", intent, "short")
        r_good = score_output("Fix the login bug with minimal changes.", intent, "short")
        assert r_bad.breakdown["safety"] < r_good.breakdown["safety"]

    def test_vague_words_penalized(self):
        intent = self._intent()
        r_vague = score_output("Do stuff and things to fix it somehow.", intent, "short")
        r_clear = score_output("Investigate and fix the login bug.", intent, "short")
        assert r_vague.breakdown["specificity"] < r_clear.breakdown["specificity"]

    def test_suggestions_list(self):
        intent = self._intent()
        result = score_output("Here is something.", intent, "short")
        assert isinstance(result.suggestions, list)

    def test_grade_mapping(self):
        s = ScoreResult(total=90, breakdown={}, suggestions=[])
        assert s.grade == "A"
        s.total = 72
        assert s.grade == "B"
        s.total = 56
        assert s.grade == "C"
        s.total = 41
        assert s.grade == "D"
        s.total = 30
        assert s.grade == "F"

    def test_to_dict(self):
        s = ScoreResult(total=75, breakdown={"specificity": 15}, suggestions=["Add action verb"])
        d = s.to_dict()
        assert d["total"] == 75
        assert d["grade"] == "B"
        assert "breakdown" in d
        assert "suggestions" in d

    def test_security_domain_alignment(self):
        intent = parse_intent("güvenlik açığı var XSS login")
        text = "Identify and fix the XSS vulnerability in the login form. Sanitize all user inputs and verify with security tests."
        result = score_output(text, intent, "agent")
        assert result.breakdown["intent_alignment"] >= 10

    def test_mode_conciseness_fast(self):
        intent = self._intent()
        # fast mode wants 20-80 words — provide text in that range
        short_text = (
            "Investigate and fix the login bug with minimal targeted changes. "
            "Identify the root cause and verify with existing tests."
        )
        result = score_output(short_text, intent, "fast")
        assert result.breakdown["conciseness"] >= 15

    def test_quality_score_in_rewrite_result(self):
        """RewriteResult.quality_score is populated from scorer."""
        from promptfix.intent import parse_intent
        from promptfix.rewriter import RewriteResult

        intent = parse_intent("fix bug")
        r = RewriteResult(
            optimized="Fix the bug with minimal changes.",
            mode="short",
            provider="groq",
            duration_ms=100,
            validation_status="valid",
            intent=intent,
            quality_score=78,
        )
        d = r.to_dict()
        assert d["quality_score"] == 78

    def test_quality_score_none_not_in_dict(self):
        """RewriteResult.quality_score=None is omitted from to_dict()."""
        from promptfix.rewriter import RewriteResult
        r = RewriteResult(
            optimized="text",
            mode="short",
            provider="groq",
            duration_ms=50,
            validation_status="valid",
            quality_score=None,
        )
        d = r.to_dict()
        assert "quality_score" not in d
