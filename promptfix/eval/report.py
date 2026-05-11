"""Report generators for evaluation results."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from promptfix.eval.runner import EvalResult


def print_table(results: list[EvalResult], console: Console | None = None) -> None:
    """Print evaluation results as a Rich table."""
    if console is None:
        console = Console()

    table = Table(
        title="PromptFix Evaluation Results",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Test", style="bold", min_width=30)
    table.add_column("Score", justify="center", width=10)
    table.add_column("Mode", width=10)
    table.add_column("Status", width=10)
    table.add_column("Duration", justify="right", width=10)

    total_score = 0
    passed = 0

    for r in results:
        score = r.final_score
        total_score += score
        status = "PASS" if r.passed else "FAIL"
        if score >= 60 and not r.passed:
            status = "WARN"

        if r.passed:
            passed += 1

        score_color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
        table.add_row(
            r.case.name,
            f"[{score_color}]{score}/100[/{score_color}]",
            r.case.mode,
            status,
            f"{r.duration_ms}ms",
        )

    avg = total_score // len(results) if results else 0
    console.print(table)
    console.print()
    console.print(Panel(
        f"[bold]Total:[/bold] {passed}/{len(results)} passed\n"
        f"[bold]Average Score:[/bold] {avg}/100\n"
        f"[bold]Provider:[/bold] {results[0].provider if results else 'N/A'}",
        title="Summary",
        border_style="green" if passed == len(results) else "yellow",
    ))


def _safe_html(text: str) -> str:
    """Escape a string for safe inclusion in HTML."""
    return html.escape(str(text))


def generate_html(results: list[EvalResult], output_path: Path | str) -> None:
    """Generate an interactive HTML report."""
    output_path = Path(output_path)

    total_score = sum(r.final_score for r in results)
    avg = total_score // len(results) if results else 0
    passed = sum(1 for r in results if r.passed)

    rows_html = ""
    for r in results:
        status_class = "pass" if r.passed else "warn" if r.final_score >= 60 else "fail"
        status_text = "PASS" if r.passed else "WARN" if r.final_score >= 60 else "FAIL"
        rule_details = "<br>".join(_safe_html(line) for line in r.rule_score.breakdown)
        llm_details = ""
        if r.llm_score:
            llm_details = (
                f"<br><strong>LLM Judge ({r.llm_score.score}/100):</strong><br>"
                f"{'<br>'.join(_safe_html(line) for line in r.llm_score.breakdown)}"
            )

        rows_html += f"""
        <tr class="{status_class}">
            <td class="name">{_safe_html(r.case.name)}</td>
            <td class="score">{r.final_score}/100</td>
            <td class="mode">{_safe_html(r.case.mode)}</td>
            <td class="status"><span class="badge {status_class}">{status_text}</span></td>
            <td class="duration">{r.duration_ms}ms</td>
            <td class="details">
                <details>
                    <summary>View</summary>
                    <div class="detail-content">
                        <p><strong>Input:</strong> {_safe_html(r.case.input)}</p>
                        <p><strong>Output:</strong> {_safe_html(r.output)}</p>
                        <p><strong>Rule Score ({r.rule_score.score}/100):</strong><br>{rule_details}</p>
                        {llm_details}
                    </div>
                </details>
            </td>
        </tr>
        """

    provider_label = _safe_html(results[0].provider) if results else "N/A"
    generated_at = _safe_html(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # Serialize data safely for inclusion in a <script> block.
    json_data = json.dumps([_result_to_dict(r) for r in results], indent=2, ensure_ascii=True)
    # Break '</script>' sequences so an attacker cannot close the script tag.
    json_data = json_data.replace("</script>", "<\\/script>")

    html_report = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PromptFix Evaluation Report</title>
    <style>
        :root {{ --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #c9d1d9; --accent: #58a6ff; --pass: #238636; --warn: #9e6a03; --fail: #da3633; }}
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace; background: var(--bg); color: var(--text); margin: 0; padding: 2rem; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: var(--accent); margin-bottom: 0.5rem; }}
        .meta {{ color: #8b949e; margin-bottom: 2rem; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; text-align: center; }}
        .card .value {{ font-size: 2rem; font-weight: bold; color: var(--accent); }}
        .card .label {{ font-size: 0.875rem; color: #8b949e; margin-top: 0.5rem; }}
        table {{ width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
        th {{ background: #21262d; padding: 0.75rem 1rem; text-align: left; font-weight: 600; border-bottom: 1px solid var(--border); }}
        td {{ padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); }}
        tr:last-child td {{ border-bottom: none; }}
        .name {{ font-weight: 600; }}
        .score {{ font-family: monospace; font-weight: bold; }}
        .badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }}
        .badge.pass {{ background: rgba(35,134,54,0.2); color: #3fb950; }}
        .badge.warn {{ background: rgba(158,106,3,0.2); color: #d29922; }}
        .badge.fail {{ background: rgba(218,54,51,0.2); color: #f85149; }}
        details {{ cursor: pointer; }}
        summary {{ color: var(--accent); font-weight: 500; }}
        .detail-content {{ margin-top: 0.5rem; padding: 1rem; background: #0d1117; border-radius: 6px; font-size: 0.875rem; }}
        .detail-content p {{ margin: 0.5rem 0; }}
        .export {{ margin-top: 2rem; text-align: right; }}
        .export a {{ color: var(--accent); text-decoration: none; margin-left: 1rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>PromptFix Evaluation Report</h1>
        <p class="meta">Generated: {generated_at} | Provider: {provider_label}</p>

        <div class="summary">
            <div class="card"><div class="value">{len(results)}</div><div class="label">Tests</div></div>
            <div class="card"><div class="value">{passed}</div><div class="label">Passed</div></div>
            <div class="card"><div class="value">{avg}</div><div class="label">Avg Score</div></div>
            <div class="card"><div class="value">{provider_label}</div><div class="label">Provider</div></div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Test</th>
                    <th>Score</th>
                    <th>Mode</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Details</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <div class="export">
            <a href="#" onclick="exportJSON()">Export JSON</a>
            <a href="#" onclick="exportCSV()">Export CSV</a>
        </div>
    </div>

    <script>
        const data = {json_data};
        function exportJSON() {{
            const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'eval-results.json'; a.click();
        }}
        function exportCSV() {{
            let csv = 'Test,Score,Mode,Status,Duration\\n';
            data.forEach(r => csv += `${{r.name}},${{r.final_score}},${{r.mode}},${{r.passed ? 'PASS' : 'FAIL'}},${{r.duration_ms}}\\n`);
            const blob = new Blob([csv], {{type: 'text/csv'}}); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'eval-results.csv'; a.click();
        }}
    </script>
</body>
</html>
"""

    output_path.write_text(html_report, encoding="utf-8")


def _result_to_dict(r: EvalResult) -> dict[str, Any]:
    return {
        "name": r.case.name,
        "input": r.case.input,
        "output": r.output,
        "mode": r.case.mode,
        "score": r.final_score,
        "rule_score": r.rule_score.score,
        "llm_score": r.llm_score.score if r.llm_score else None,
        "passed": r.passed,
        "duration_ms": r.duration_ms,
        "provider": r.provider,
    }
