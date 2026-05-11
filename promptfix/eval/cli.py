"""Eval CLI command for promptfix."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

import promptfix
from promptfix.eval.runner import load_suite, run_eval
from promptfix.eval.report import print_table, generate_html
from promptfix.config import load_config
from promptfix.rewriter import create_provider

app = typer.Typer(help="PromptFix Evaluation Center", invoke_without_command=True)
console = Console()

# Resolve default evals dir relative to the promptfix package
_DEFAULT_EVAL_DIR = str(Path(promptfix.__file__).parent.parent / "evals")


class _StubProvider:
    """Deterministic provider used when no API key is available.

    Produces rule-compliant output so the scoring framework can be
    exercised in CI environments without secrets.
    """

    model = "stub"

    def complete(self, messages: list[dict]) -> str:
        from promptfix.guard import get_fallback
        from promptfix.intent import parse_intent
        # Pull the user's original text from the last user message
        user_text = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        intent = parse_intent(user_text)
        return get_fallback(intent)

    def stream_complete(self, messages: list[dict]):
        yield self.complete(messages)

    def health_check(self):
        return True, "stub (no API key -- deterministic fallback mode)"


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    suite: str = typer.Option(_DEFAULT_EVAL_DIR, "--suite", "-s", help="Path to eval suite YAML or directory"),
    judge: bool = typer.Option(False, "--judge", "-j", help="Enable LLM-based judge (slower, costs tokens)"),
    report: str = typer.Option(None, "--report", "-r", help="Generate HTML report to file path"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
    ci: bool = typer.Option(False, "--ci", help="CI mode: exit non-zero if any test fails"),
    threshold: int = typer.Option(75, "--threshold", "-t", help="Minimum passing score (CI mode)"),
):
    """Run the PromptFix evaluation suite."""
    if ctx.invoked_subcommand is not None:
        return

    config = load_config()

    provider = None
    try:
        provider = create_provider(config)
    except RuntimeError as e:
        if judge:
            console.print(f"[red]Provider error: {e}[/red]")
            raise typer.Exit(1)
        console.print(f"[yellow]WARNING: No provider available ({e.__class__.__name__}). Using deterministic stub -- LLM quality not tested.[/yellow]")
        provider = _StubProvider()

    suite_path = Path(suite)
    if not suite_path.exists():
        console.print(f"[red]Suite not found: {suite}[/red]")
        raise typer.Exit(1)

    cases = load_suite(suite_path)
    if not cases:
        console.print("[yellow]No test cases found.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[dim]Running {len(cases)} test cases...[/dim]\n")

    results = run_eval(cases, provider=provider, config=config, use_llm_judge=judge)

    if format == "json":
        data = [{
            "name": r.case.name,
            "score": r.final_score,
            "passed": r.passed,
            "mode": r.case.mode,
            "duration_ms": r.duration_ms,
            "output": r.output,
        } for r in results]
        console.print_json(data, indent=2)
    else:
        print_table(results, console)

    if report:
        generate_html(results, report)
        console.print(f"\n[green]Report saved to {report}[/green]")

    if ci:
        failed = [r for r in results if r.final_score < threshold]
        if failed:
            console.print(f"\n[red]CI failed: {len(failed)} tests below threshold ({threshold})[/red]")
            raise typer.Exit(1)
        console.print(f"\n[green]CI passed: all tests >= {threshold}[/green]")
