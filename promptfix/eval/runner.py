"""PromptFix Evaluation Center - Core engine."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from promptfix.eval.scorer import ScoreResult, run_assertions, run_llm_judge
from promptfix.rewriter import rewrite, create_provider
from promptfix.config import load_config


@dataclass
class EvalCase:
    name: str
    input: str
    mode: str = "short"
    project_hints: dict[str, Any] | None = None
    asserts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvalResult:
    case: EvalCase
    output: str
    duration_ms: int
    rule_score: ScoreResult
    llm_score: ScoreResult | None = None
    provider: str = ""

    @property
    def final_score(self) -> int:
        if self.llm_score:
            return int(self.rule_score.score * 0.6 + self.llm_score.score * 0.4)
        return self.rule_score.score

    @property
    def passed(self) -> bool:
        return self.final_score >= 75


def load_suite(path: Path | str) -> list[EvalCase]:
    """Load test cases from a YAML suite file or directory."""
    path = Path(path)
    cases: list[EvalCase] = []

    if path.is_dir():
        for f in sorted(path.glob("*.yaml")):
            cases.extend(_load_yaml_file(f))
    else:
        cases.extend(_load_yaml_file(path))

    return cases


def _load_yaml_file(path: Path) -> list[EvalCase]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(
            f"Invalid YAML in eval suite: {path}\n"
            f"Hint: check indentation and special characters.\n"
            f"Detail: {exc}"
        ) from exc
    cases = []
    for item in raw.get("tests", []):
        cases.append(EvalCase(
            name=item.get("name", "unnamed"),
            input=item.get("input", ""),
            mode=item.get("mode", "short"),
            project_hints=item.get("project_hints"),
            asserts=item.get("asserts", []),
        ))
    return cases


def run_eval(
    cases: list[EvalCase],
    provider=None,
    config: dict | None = None,
    use_llm_judge: bool = False,
) -> list[EvalResult]:
    """Run evaluation suite and return results."""
    if config is None:
        config = load_config()
    if provider is None:
        provider = create_provider(config)

    provider_name = config.get("provider", "unknown")
    results: list[EvalResult] = []

    for case in cases:
        start = time.time()
        try:
            result = rewrite(
                text=case.input,
                mode=case.mode,
                config=config,
                provider=provider,
                project_hints=case.project_hints,
                source="eval",
            )
            output = result.optimized
        except Exception as e:
            output = f"ERROR: {e}"

        elapsed_ms = int((time.time() - start) * 1000)

        # Rule-based scoring
        rule_score = run_assertions(output, case.asserts, case.input)

        # Optional LLM judge
        llm_score = None
        if use_llm_judge:
            try:
                llm_score = run_llm_judge(output, case.input, case.mode, provider)
            except Exception:
                pass

        results.append(EvalResult(
            case=case,
            output=output,
            duration_ms=elapsed_ms,
            rule_score=rule_score,
            llm_score=llm_score,
            provider=provider_name,
        ))

    return results
