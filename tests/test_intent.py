"""Tests for the intent parser."""

import pytest

from promptfix.intent import parse_intent


class TestTaskTypeClassification:
    def test_bugfix_turkish(self):
        intent = parse_intent("login token refresh bozuldu başka yeri bozma")
        assert intent.task_type == "bugfix"

    def test_bugfix_english(self):
        intent = parse_intent("the auth token refresh is broken, don't touch other code")
        assert intent.task_type == "bugfix"

    def test_bugfix_calismıyor(self):
        intent = parse_intent("ödeme çalışmıyor")
        assert intent.task_type == "bugfix"

    def test_bugfix_patlıyor(self):
        intent = parse_intent("api patlıyor bazen")
        assert intent.task_type == "bugfix"

    def test_performance_turkish(self):
        intent = parse_intent("dashboard yavaş render kontrol et")
        assert intent.task_type == "performance"

    def test_performance_kasiyor(self):
        intent = parse_intent("sayfa kasıyor scroll yaparken")
        assert intent.task_type == "performance"

    def test_feature(self):
        intent = parse_intent("add a new endpoint for user preferences")
        assert intent.task_type == "feature"

    def test_feature_turkish_ekle(self):
        intent = parse_intent("dark mode ekle settings sayfasına")
        assert intent.task_type == "feature"

    def test_review(self):
        intent = parse_intent("projeyi incele küçük iyileştirme yap")
        assert intent.task_type == "review"

    def test_refactor_explicit(self):
        intent = parse_intent("refactor the payment module")
        assert intent.task_type == "refactor"

    def test_test_task(self):
        intent = parse_intent("write tests for the auth module")
        assert intent.task_type == "test"

    def test_docs_task(self):
        intent = parse_intent("update the readme docs")
        assert intent.task_type == "docs"


class TestDomainClassification:
    def test_auth_domain(self):
        intent = parse_intent("login token refresh bozuldu")
        assert intent.domain == "auth"

    def test_payment_domain(self):
        intent = parse_intent("ödeme indirim checkout çalışmıyor")
        assert intent.domain == "payment"

    def test_checkout_domain(self):
        intent = parse_intent("checkout sepet cart boş geliyor")
        assert intent.domain == "checkout"

    def test_api_domain(self):
        intent = parse_intent("api endpoint returns 500")
        assert intent.domain == "api"

    def test_database_domain(self):
        intent = parse_intent("migration schema broke the db")
        assert intent.domain == "database"

    def test_ui_domain(self):
        intent = parse_intent("dashboard render performance is bad")
        assert intent.domain == "dashboard"

    def test_cli_domain(self):
        intent = parse_intent("cli command flag parse broken")
        assert intent.domain == "cli"


class TestConstraints:
    def test_minimal_changes(self):
        intent = parse_intent("login token refresh bozuldu başka yeri bozma")
        assert "minimal_changes" in intent.constraints
        assert "avoid_unrelated_changes" in intent.constraints

    def test_elleme_constraint(self):
        intent = parse_intent("cart bug var elleme diğerlerini")
        assert "minimal_changes" in intent.constraints

    def test_abartma_constraint(self):
        intent = parse_intent("login fix et abartma")
        assert "minimal_changes" in intent.constraints

    def test_no_constraints(self):
        intent = parse_intent("add a new feature for dashboards")
        assert intent.constraints == []

    def test_refactor_not_allowed(self):
        intent = parse_intent("fix the bug minimal başka yeri bozma")
        assert intent.allow_refactor is False

    def test_refactor_allowed_when_explicit(self):
        intent = parse_intent("refactor the auth module minimal changes")
        assert intent.allow_refactor is True


class TestCasualAddress:
    def test_strips_kral(self):
        intent = parse_intent("kral login bozuldu")
        assert "kral" not in intent.normalized_text.lower()

    def test_strips_knk(self):
        intent = parse_intent("knk token patlıyor")
        assert "knk" not in intent.normalized_text.lower()

    def test_strips_multiple(self):
        intent = parse_intent("aga reis token patlıyor")
        assert "aga" not in intent.normalized_text.lower()
        assert "reis" not in intent.normalized_text.lower()

    def test_strips_hocam(self):
        intent = parse_intent("hocam api 500 dönüyor")
        assert "hocam" not in intent.normalized_text.lower()

    def test_preserves_technical_words(self):
        intent = parse_intent("kral login token refresh bozuldu")
        assert "login" in intent.normalized_text.lower()
        assert "token" in intent.normalized_text.lower()
        assert "refresh" in intent.normalized_text.lower()


class TestNeedsContext:
    def test_project_level(self):
        intent = parse_intent("projeyi incele küçük iyileştirme yap")
        assert intent.needs_context is True

    def test_specific_bugfix(self):
        intent = parse_intent("login token refresh bozuldu başka yeri bozma")
        assert intent.needs_context is False

    def test_feature_needs_context(self):
        intent = parse_intent("implement a new dashboard widget")
        assert intent.needs_context is True


class TestTurkishCodingPrompts:
    """Integration tests for real-world Turkish coding prompts."""

    def test_auth_bugfix_with_constraint(self):
        intent = parse_intent("kral login token refresh bozuldu başka yeri bozma")
        assert intent.task_type == "bugfix"
        assert intent.domain == "auth"
        assert "minimal_changes" in intent.constraints
        assert intent.allow_refactor is False
        assert "kral" not in intent.normalized_text.lower()

    def test_payment_checkout_bug(self):
        intent = parse_intent("ödeme indirim checkout çalışmıyor")
        assert intent.task_type == "bugfix"
        assert intent.domain == "payment"

    def test_api_timeout_with_constraint(self):
        intent = parse_intent("knk api endpoint 500 dönüyor bazen timeout oluyor başka yeri elleme")
        assert intent.task_type == "bugfix"
        assert intent.domain == "api"
        assert "minimal_changes" in intent.constraints
        assert "knk" not in intent.normalized_text.lower()

    def test_db_migration_feature(self):
        intent = parse_intent("database migration schema ekle user_preferences table")
        assert intent.domain == "database"
        assert intent.task_type == "feature"

    def test_performance_dashboard(self):
        intent = parse_intent("dashboard yavaş render kontrol et")
        assert intent.task_type == "performance"
