"""Prompt diff utility — compares original and optimized prompts.

Uses only Python stdlib (difflib). No external dependencies required.

Public API:
    compute_diff(original, optimized) -> DiffResult
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class DiffResult:
    """Result of comparing original vs optimized prompt text."""

    original: str
    optimized: str
    # Human-readable unified diff (empty string when texts are identical)
    unified: str
    # True when original and optimized are identical after stripping
    unchanged: bool

    def to_dict(self) -> dict:
        return {
            "unified": self.unified,
            "unchanged": self.unchanged,
        }


def compute_diff(original: str, optimized: str) -> DiffResult:
    """Return a DiffResult comparing *original* and *optimized*.

    The unified diff uses word-level splitting so the result is more
    readable than a raw character diff, while still being compact enough
    for large prompts.

    Performance: difflib operates in O(n*m) time on sequence length.
    For typical prompt lengths (< 500 words) this is instantaneous.
    For very long texts the char-limit on history entries (MAX_HISTORY)
    already caps the effective input, so no extra truncation is needed.
    """
    orig_stripped = original.strip()
    opt_stripped = optimized.strip()

    if orig_stripped == opt_stripped:
        return DiffResult(
            original=orig_stripped,
            optimized=opt_stripped,
            unified="",
            unchanged=True,
        )

    # Split into lines for a cleaner diff output.
    # Each "line" is a sentence-ish fragment (split on ". " and newlines).
    orig_lines = _to_lines(orig_stripped)
    opt_lines = _to_lines(opt_stripped)

    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            opt_lines,
            fromfile="original",
            tofile="optimized",
            lineterm="",
        )
    )

    unified = "\n".join(diff_lines)

    return DiffResult(
        original=orig_stripped,
        optimized=opt_stripped,
        unified=unified,
        unchanged=False,
    )


def _to_lines(text: str) -> list[str]:
    """Split text into displayable lines for difflib."""
    # Normalise line endings, then split on newlines.
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # Filter empty lines but keep non-empty ones with a trailing newline
    # so difflib output looks clean.
    return [line + "\n" for line in lines if line.strip()]


def format_diff_rich(diff_result: DiffResult) -> str:
    """Return a Rich-markup string for pretty CLI output.

    Lines starting with '+' are highlighted green (additions),
    lines starting with '-' are highlighted red (removals),
    header lines ('---', '+++', '@@') are shown in dim.
    """
    if diff_result.unchanged:
        return "[dim]No changes — original and optimized are identical.[/dim]"

    lines = diff_result.unified.splitlines()
    rendered: list[str] = []
    for line in lines:
        if line.startswith("+++") or line.startswith("---"):
            rendered.append(f"[dim]{_escape_markup(line)}[/dim]")
        elif line.startswith("@@"):
            rendered.append(f"[dim cyan]{_escape_markup(line)}[/dim cyan]")
        elif line.startswith("+"):
            rendered.append(f"[green]{_escape_markup(line)}[/green]")
        elif line.startswith("-"):
            rendered.append(f"[red]{_escape_markup(line)}[/red]")
        else:
            rendered.append(_escape_markup(line))
    return "\n".join(rendered)


def _escape_markup(text: str) -> str:
    """Escape Rich markup special characters in user text."""
    return text.replace("[", "\\[").replace("]", "\\]")
