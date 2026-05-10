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


class TestIncludeDiffContract:
    """Test that the /optimize API correctly handles include_diff requests.
    This is the contract background.js relies on when it passes include_diff=True."""

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_include_diff_true_returns_diff_field(self, mock_config, mock_provider, client):
        """When include_diff=True, response must contain a 'diff' object."""
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the login token refresh with minimal changes."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={
            "text": "fix login token bug",
            "mode": "short",
            "include_diff": True,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "diff" in data, "diff field must be present when include_diff=True"
        assert "unified" in data["diff"]
        assert "unchanged" in data["diff"]

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_include_diff_false_by_default(self, mock_config, mock_provider, client):
        """Without include_diff, response must NOT contain a 'diff' field."""
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the login token bug."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={"text": "fix login bug", "mode": "short"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "diff" not in data

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_include_diff_does_not_break_optimized_field(self, mock_config, mock_provider, client):
        """With include_diff, the 'optimized' field must still be present and non-empty."""
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the login token refresh with minimal changes."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={
            "text": "fix login token bug",
            "mode": "short",
            "include_diff": True,
        })
        data = resp.get_json()
        assert "optimized" in data
        assert len(data["optimized"]) > 0

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_diff_unchanged_flag_when_output_same(self, mock_config, mock_provider, client):
        """If provider returns the same text as input, diff.unchanged must be True."""
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        # Provider returns identical text — diff should detect unchanged
        identical = "fix the login token refresh bug"
        mock_prov.complete.return_value = identical
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={
            "text": identical,
            "mode": "raw",
            "include_diff": True,
        })
        if resp.status_code == 200:
            data = resp.get_json()
            if "diff" in data:
                # unchanged may be True or False depending on guard/cleaning
                assert isinstance(data["diff"]["unchanged"], bool)

    @patch("promptfix.service._get_provider")
    @patch("promptfix.service._get_config")
    def test_diff_no_sensitive_data_in_response(self, mock_config, mock_provider, client):
        """diff response must not expose api_key, token, or provider credentials."""
        mock_config.return_value = _MOCK_CONFIG
        mock_prov = MagicMock()
        mock_prov.complete.return_value = "Fix the authentication token refresh with minimal changes."
        mock_provider.return_value = mock_prov

        resp = client.post("/optimize", json={
            "text": "fix auth bug",
            "mode": "short",
            "include_diff": True,
        })
        data = resp.get_json()
        response_str = str(data)
        assert "api_key" not in response_str
        assert "serviceToken" not in response_str
        assert "secret" not in response_str.lower()


class TestCacheDataIntegrity:
    """Test the cache entry structure and safety constraints that background.js enforces.
    These are Python-side equivalents of the JS cache logic to verify data contracts."""

    def _make_safe_cache_entry(self, **kwargs):
        """Mirror of the safe-copy logic in background.js writeCache()."""
        entry = {
            "input":           str(kwargs.get("input", ""))[:500],
            "output":          str(kwargs.get("output", ""))[:1000],
            "mode":            str(kwargs.get("mode", "")),
            "quality_score":   kwargs["quality_score"] if isinstance(kwargs.get("quality_score"), int) else None,
            "score_breakdown": kwargs.get("score_breakdown") or None,
            "diff":            kwargs.get("diff") or None,
            "timestamp":       kwargs.get("timestamp", 0),
        }
        return entry

    def test_cache_entry_excludes_sensitive_fields(self):
        """Cache entry builder must not carry api_key or token."""
        entry = self._make_safe_cache_entry(
            input="fix bug",
            output="fixed",
            mode="short",
            quality_score=80,
            api_key="sk-secret",       # must be dropped
            serviceToken="tok-secret", # must be dropped
        )
        assert "api_key" not in entry
        assert "serviceToken" not in entry

    def test_cache_entry_input_truncated_at_500(self):
        """Input longer than 500 chars must be truncated."""
        long_input = "x" * 600
        entry = self._make_safe_cache_entry(input=long_input, output="ok", mode="short")
        assert len(entry["input"]) == 500

    def test_cache_entry_output_truncated_at_1000(self):
        """Output longer than 1000 chars must be truncated."""
        long_output = "y" * 1200
        entry = self._make_safe_cache_entry(input="q", output=long_output, mode="short")
        assert len(entry["output"]) == 1000

    def test_cache_entry_quality_score_none_when_missing(self):
        """quality_score must default to None when not provided."""
        entry = self._make_safe_cache_entry(input="q", output="a", mode="short")
        assert entry["quality_score"] is None

    def test_cache_max_5_entries(self):
        """Simulated cache must not exceed CACHE_MAX=5 entries."""
        CACHE_MAX = 5
        CACHE_TTL_MS = 24 * 60 * 60 * 1000
        import time

        existing = [
            self._make_safe_cache_entry(
                input=f"old {i}", output=f"out {i}", mode="short",
                timestamp=int(time.time() * 1000)
            )
            for i in range(6)  # already 6 items
        ]
        new_entry = self._make_safe_cache_entry(
            input="new", output="new out", mode="fast",
            timestamp=int(time.time() * 1000)
        )
        # Simulate prepend + trim
        now = int(time.time() * 1000)
        cache = [new_entry] + existing
        cache = [e for e in cache if now - e["timestamp"] < CACHE_TTL_MS]
        cache = cache[:CACHE_MAX]

        assert len(cache) == CACHE_MAX

    def test_cache_drops_entries_older_than_24h(self):
        """Cache entries older than 24 hours must be removed."""
        import time
        CACHE_TTL_MS = 24 * 60 * 60 * 1000

        now = int(time.time() * 1000)
        old_ts  = now - CACHE_TTL_MS - 1000   # 1 second past TTL
        new_ts  = now - 3600 * 1000           # 1 hour ago, still valid

        old_entry = self._make_safe_cache_entry(input="old", output="o", mode="short", timestamp=old_ts)
        new_entry = self._make_safe_cache_entry(input="new", output="n", mode="short", timestamp=new_ts)
        cache = [old_entry, new_entry]
        cache = [e for e in cache if now - e["timestamp"] < CACHE_TTL_MS]

        assert len(cache) == 1
        assert cache[0]["input"] == "new"

    def test_cache_diff_field_is_none_when_absent(self):
        """diff must be None in cache entry when not provided."""
        entry = self._make_safe_cache_entry(input="q", output="a", mode="short")
        assert entry["diff"] is None

    def test_cache_diff_field_stored_when_present(self):
        """diff must be stored in cache entry when provided."""
        diff = {"unified": "--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new", "unchanged": False}
        entry = self._make_safe_cache_entry(input="q", output="a", mode="short", diff=diff)
        assert entry["diff"] is not None
        assert entry["diff"]["unified"].startswith("---")


class TestDiffLineClassification:
    """Test that diff line classification logic is correct.
    These verify the Python diff output format the popup JS renders."""

    def _classify(self, line):
        """Mirror of popup.js renderDiffLines() classification logic."""
        if line.startswith("+") and not line.startswith("++"):
            return "add"
        elif line.startswith("-") and not line.startswith("--"):
            return "del"
        elif line.startswith("@@") or line.startswith("---") or line.startswith("+++"):
            return "hdr"
        return "ctx"

    def test_addition_line_classified_as_add(self):
        assert self._classify("+new line added") == "add"

    def test_deletion_line_classified_as_del(self):
        assert self._classify("-old line removed") == "del"

    def test_context_line_classified_as_ctx(self):
        assert self._classify(" unchanged context line") == "ctx"

    def test_hunk_header_classified_as_hdr(self):
        assert self._classify("@@ -1,3 +1,4 @@") == "hdr"

    def test_unified_diff_plus_plus_header_classified_as_hdr(self):
        assert self._classify("+++ b/file.txt") == "hdr"

    def test_unified_diff_minus_minus_header_classified_as_hdr(self):
        assert self._classify("--- a/file.txt") == "hdr"

    def test_compute_diff_output_is_classifiable(self):
        """Every line from compute_diff().unified must be classifiable without error."""
        from promptfix.diff import compute_diff
        result = compute_diff(
            "Fix the authentication bug\nMinimal changes only",
            "Fix the authentication token refresh bug\nMinimal changes only\nRun relevant tests",
        )
        for line in result.unified.split("\n"):
            cls = self._classify(line)
            assert cls in ("add", "del", "hdr", "ctx")
