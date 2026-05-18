"""Tests for the hotkey clipboard flow logic.

The actual hotkey registration and tray are OS-dependent and tested manually.
These tests verify the rewrite pipeline that hotkeys use.
"""

from unittest.mock import MagicMock

from promptfix.rewriter import rewrite


class TestHotkeyRewriteFlow:
    """Simulate the hotkey flow: text in -> rewrite -> text out."""

    def _make_config(self):
        return {
            "provider": "groq",
            "default_mode": "short",
            "validation": {
                "enabled": True,
                "retry_on_invalid": True,
                "deterministic_fallback": True,
            },
        }

    def test_short_mode_flow(self):
        """Simulate Ctrl+Alt+S flow."""
        mock = MagicMock()
        mock.complete.return_value = (
            "Investigate and fix the login token refresh issue "
            "with minimal, targeted changes."
        )

        result = rewrite(
            text="login token refresh bozuldu başka yeri bozma",
            mode="short",
            config=self._make_config(),
            provider=mock,
        )

        assert result.optimized
        assert result.mode == "short"
        # Output must be pasteable — no fences, no quotes
        assert not result.optimized.startswith("```")
        assert not result.optimized.startswith('"')
        assert not result.optimized.lower().startswith("here is")

    def test_agent_mode_flow(self):
        """Simulate Ctrl+Alt+P flow."""
        mock = MagicMock()
        mock.complete.return_value = (
            "Task:\nFix login token refresh\n\n"
            "Context:\nauth module\n\n"
            "Instructions:\n- Inspect refresh flow\n\n"
            "Constraints:\n- Minimal changes\n\n"
            "Validation:\n- Run auth tests\n\n"
            "Deliverables:\n- Working token refresh"
        )

        result = rewrite(
            text="login token refresh bozuldu",
            mode="agent",
            config=self._make_config(),
            provider=mock,
        )

        assert result.mode == "agent"
        assert "Task:" in result.optimized

    def test_raw_mode_flow(self):
        """Simulate Ctrl+Alt+R flow."""
        mock = MagicMock()
        mock.complete.return_value = "Fix the login bug."

        result = rewrite(
            text="fix login",
            mode="raw",
            config=self._make_config(),
            provider=mock,
        )

        assert result.mode == "raw"

    def test_empty_clipboard_noop(self):
        """If clipboard was empty (nothing selected), should handle gracefully."""
        mock = MagicMock()
        mock.complete.return_value = "Investigate the issue."

        # Empty text should still work through the pipeline
        result = rewrite(
            text="  ",
            mode="short",
            config={
                "provider": "groq",
                "default_mode": "short",
                "validation": {"enabled": False},
            },
            provider=mock,
        )
        assert result.optimized
        # The rewriter still runs (whitespace is passed through)
        # The hotkey handler should check for empty *before* calling rewrite

    def test_fallback_still_pasteable(self):
        """Even on fallback, the output must be clean pasteable text."""
        mock = MagicMock()
        mock.complete.return_value = "Project overview: this is a React app."

        result = rewrite(
            text="login token refresh bozuldu",
            mode="short",
            config=self._make_config(),
            provider=mock,
        )

        assert result.validation_status == "fallback"
        # Fallback output must be clean
        assert not result.optimized.startswith("```")
        assert not result.optimized.startswith('"')
        assert "Investigate" in result.optimized
