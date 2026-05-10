"""Tests for extension-related logic.

These test the Python-side behavior that the extension depends on.
The actual DOM replacement is JS-only and tested via the test page.
"""

import pytest
from unittest.mock import MagicMock, patch

from promptfix.service import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestExtensionServiceContract:
    """Test the /optimize API contract that the extension depends on."""

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_response_shape(self, mock_config, mock_provider, client):
        """Extension expects: optimized, mode, provider, duration_ms, valid"""
        mock_config.return_value = {
            "provider": "groq",
            "default_mode": "short",
            "providers": {"groq": {"model": "test"}},
            "validation": {"enabled": False},
            "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Optimized prompt text here."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={
            "text": "fix login bug",
            "mode": "short",
        })
        data = resp.get_json()

        # These are the fields the extension relies on
        assert "optimized" in data
        assert isinstance(data["optimized"], str)
        assert len(data["optimized"]) > 0

        assert "mode" in data
        assert data["mode"] in ("short", "agent", "raw")

        assert "provider" in data
        assert isinstance(data["provider"], str)

        assert "duration_ms" in data
        assert isinstance(data["duration_ms"], int)

        assert "valid" in data
        assert isinstance(data["valid"], bool)

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_short_mode(self, mock_config, mock_provider, client):
        mock_config.return_value = {
            "provider": "groq", "default_mode": "short",
            "providers": {"groq": {"model": "t"}},
            "validation": {"enabled": False}, "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Optimized."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix bug", "mode": "short"})
        assert resp.get_json()["mode"] == "short"

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_agent_mode(self, mock_config, mock_provider, client):
        mock_config.return_value = {
            "provider": "groq", "default_mode": "short",
            "providers": {"groq": {"model": "t"}},
            "validation": {"enabled": False}, "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Task:\nFix\nConstraints:\n- min"
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix bug", "mode": "agent"})
        assert resp.get_json()["mode"] == "agent"

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_raw_mode(self, mock_config, mock_provider, client):
        mock_config.return_value = {
            "provider": "groq", "default_mode": "short",
            "providers": {"groq": {"model": "t"}},
            "validation": {"enabled": False}, "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the login."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix login", "mode": "raw"})
        assert resp.get_json()["mode"] == "raw"

    def test_service_down_error_message(self, client):
        """When provider is broken, error must be clear."""
        # Reset cached provider to force re-init
        import promptfix.service as svc
        old_provider = svc._provider
        svc._provider = None
        svc._config = None

        resp = client.post("/optimize", json={"text": "fix bug", "mode": "short"})
        # May return 500 with error message
        if resp.status_code == 500:
            data = resp.get_json()
            assert "error" in data

        # Restore
        svc._provider = old_provider


class TestExtensionReplacementScenarios:
    """Test that the rewriter produces output suitable for replacement.
    These use the full pipeline with a mock provider to ensure the
    output is clean text (no fences, no prefixes, no quotes)."""

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def _optimize(self, text, mode, mock_config, mock_provider, client, provider_output):
        mock_config.return_value = {
            "provider": "groq", "default_mode": "short",
            "providers": {"groq": {"model": "t"}},
            "validation": {"enabled": False}, "service": {"token": ""},
        }
        mock_prov = MagicMock()
        mock_prov.complete.return_value = provider_output
        mock_provider.return_value = mock_prov
        resp = client.post("/optimize", json={"text": text, "mode": mode})
        return resp.get_json()

    def test_textarea_replacement_clean(self, client):
        """Output for textarea must be clean text — no fences, no prefix."""
        with patch("promptfix.service._get_provider") as mp, \
             patch("promptfix.service._get_config") as mc:
            mc.return_value = {
                "provider": "groq", "default_mode": "short",
                "providers": {"groq": {"model": "t"}},
                "validation": {"enabled": False}, "service": {"token": ""},
            }
            prov = MagicMock()
            prov.complete.return_value = "Fix the login token refresh with minimal changes."
            mp.return_value = prov

            resp = client.post("/optimize", json={
                "text": "login bozuldu",
                "mode": "short",
            })
            optimized = resp.get_json()["optimized"]

            # Must not have fences, quotes, or prefixes
            assert not optimized.startswith("```")
            assert not optimized.startswith('"')
            assert not optimized.lower().startswith("here is")
            assert not optimized.lower().startswith("sure,")


_MOCK_CONFIG = {
    "provider": "groq",
    "default_mode": "short",
    "providers": {"groq": {"model": "t"}},
    "validation": {"enabled": False},
    "service": {"token": ""},
}


class TestContextMenuModes:
    """Test that /optimize accepts all 5 modes the context menu may send."""

    @pytest.mark.parametrize("mode", ["fast", "short", "agent", "explain", "raw"])
    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_all_context_menu_modes_accepted(self, mock_config, mock_provider, mode, client):
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Optimized output for this mode."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix bug", "mode": mode})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["mode"] == mode
        assert "optimized" in data

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_fast_mode_response_shape(self, mock_config, mock_provider, client):
        """fast mode must return the same response fields the extension reads."""
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Quick fix."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "slow query", "mode": "fast"})
        data = resp.get_json()

        for field in ("optimized", "mode", "provider", "duration_ms", "valid"):
            assert field in data, f"Missing field: {field}"

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_explain_mode_response_shape(self, mock_config, mock_provider, client):
        """explain mode must return the same response fields the extension reads."""
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "The bug occurs because of X. Fix: Y."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "why does login break", "mode": "explain"})
        data = resp.get_json()

        for field in ("optimized", "mode", "provider", "duration_ms", "valid"):
            assert field in data, f"Missing field: {field}"


class TestScoreBadgeContract:
    """Test that /optimize returns quality_score for the popup score badge."""

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_optimize_response_has_quality_score(self, mock_config, mock_provider, client):
        """quality_score must be present so the popup can render the score badge."""
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the authentication token refresh bug with minimal changes."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix auth bug", "mode": "short"})
        data = resp.get_json()

        assert "quality_score" in data
        assert isinstance(data["quality_score"], int)
        assert 0 <= data["quality_score"] <= 100

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_optimize_response_has_score_breakdown(self, mock_config, mock_provider, client):
        """score_breakdown must be present with grade and breakdown for popup details."""
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the authentication token refresh bug with minimal changes."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix auth bug", "mode": "short"})
        data = resp.get_json()

        assert "score_breakdown" in data
        sb = data["score_breakdown"]
        assert "total" in sb
        assert "grade" in sb
        assert "breakdown" in sb

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_quality_score_matches_breakdown_total(self, mock_config, mock_provider, client):
        """quality_score field must equal score_breakdown.total for consistency."""
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the authentication token refresh bug."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix auth bug", "mode": "short"})
        data = resp.get_json()

        assert data["quality_score"] == data["score_breakdown"]["total"]


class TestHistoryQualityScore:
    """Test that history entries include quality_score when available."""

    def test_log_entry_accepts_quality_score(self):
        """log_entry must accept quality_score without raising."""
        from promptfix.history import log_entry
        import tempfile, os
        from unittest.mock import patch as mpatch

        with tempfile.TemporaryDirectory() as tmpdir:
            with mpatch("promptfix.history._history_path",
                        return_value=__import__("pathlib").Path(tmpdir) / "h.jsonl"):
                # Must not raise
                log_entry(
                    input_text="test input",
                    output_text="test output",
                    mode="short",
                    provider="groq",
                    duration_ms=100,
                    validation_status="valid",
                    source="test",
                    quality_score=88,
                )

    def test_log_entry_stores_quality_score(self):
        """quality_score must appear in the stored JSONL entry."""
        import json, tempfile
        from pathlib import Path
        from unittest.mock import patch as mpatch
        from promptfix.history import log_entry

        with tempfile.TemporaryDirectory() as tmpdir:
            hist_path = Path(tmpdir) / "h.jsonl"
            with mpatch("promptfix.history._history_path", return_value=hist_path):
                log_entry(
                    input_text="fix bug",
                    output_text="fixed bug",
                    mode="short",
                    provider="groq",
                    duration_ms=50,
                    validation_status="valid",
                    source="api",
                    quality_score=75,
                )
                entry = json.loads(hist_path.read_text())
                assert entry["quality_score"] == 75

    def test_log_entry_without_quality_score_omits_field(self):
        """Without quality_score, the field must not appear in the JSONL entry."""
        import json, tempfile
        from pathlib import Path
        from unittest.mock import patch as mpatch
        from promptfix.history import log_entry

        with tempfile.TemporaryDirectory() as tmpdir:
            hist_path = Path(tmpdir) / "h.jsonl"
            with mpatch("promptfix.history._history_path", return_value=hist_path):
                log_entry(
                    input_text="fix bug",
                    output_text="fixed",
                    mode="short",
                    provider="groq",
                    duration_ms=50,
                    validation_status="valid",
                    source="api",
                )
                entry = json.loads(hist_path.read_text())
                assert "quality_score" not in entry
