"""Tests for the ContextLite layer."""


from promptfix.context import SAFE_RULES, build_context
from promptfix.intent import parse_intent


class TestContextLimits:
    def test_raw_mode_no_context(self):
        intent = parse_intent("fix the login bug")
        ctx = build_context(intent, "raw")
        assert ctx == ""

    def test_fast_mode_under_limit(self):
        intent = parse_intent("fix the login bug")
        ctx = build_context(intent, "fast")
        assert len(ctx) <= 300

    def test_short_mode_under_limit(self):
        intent = parse_intent("fix the login bug")
        ctx = build_context(intent, "short", {"name": "MyApp", "stack": "React + Node"})
        assert len(ctx) <= 600

    def test_agent_mode_includes_hints(self):
        intent = parse_intent("fix the login bug")
        ctx = build_context(intent, "agent", {
            "name": "MyApp",
            "stack": "React + Node + Postgres",
            "test_cmd": "npm test",
            "relevant_paths": ["src/auth/", "src/middleware/"],
        })
        assert "MyApp" in ctx
        assert "React" in ctx
        assert "npm test" in ctx


class TestSafeRules:
    def test_always_includes_safe_rules(self):
        intent = parse_intent("add a new feature")
        ctx = build_context(intent, "short")
        assert "minimal" in ctx.lower() or "changes" in ctx.lower()

    def test_safe_rules_content(self):
        assert "secrets" in SAFE_RULES.lower()
        assert "test" in SAFE_RULES.lower()


class TestProjectHints:
    def test_no_hints_still_works(self):
        intent = parse_intent("fix the bug")
        ctx = build_context(intent, "short")
        assert ctx  # should still have safe rules

    def test_relevant_paths_included(self):
        intent = parse_intent("fix the api endpoint")
        ctx = build_context(intent, "agent", {
            "relevant_paths": ["src/api/routes.ts", "src/api/middleware.ts"],
        })
        assert "src/api" in ctx
