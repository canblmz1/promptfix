# Contributing to PromptFix

Thank you for your interest in contributing to PromptFix! This document provides guidelines and instructions for contributing.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Install in development mode**:
   ```bash
   pip install -e ".[dev]"
   ```

## Development Workflow

### Running Tests

```bash
pytest -v
```

All **291+** tests must pass before submitting a PR.

### Running the Evaluation Suite

```bash
# Full suite with real provider (requires API key)
promptfix eval

# CI mode — fails if any test drops below threshold
promptfix eval --ci --threshold 75

# Stub mode — deterministic fallback, no API key needed (rule-based scoring only)
promptfix eval

# Generate HTML report
promptfix eval --report eval-report.html
```

**Note:** Without an API key, the evaluator runs in stub mode. This still validates rule-based assertions but does **not** test LLM output quality. To test with a real provider, set `GROQ_API_KEY` or configure Ollama.

The CI threshold is **75/100**. Ensure your changes don't drop the evaluation score.

### Code Style

- Follow PEP 8
- Use type hints where possible
- Add docstrings for public functions
- Keep functions focused and small

## Adding New Features

### Adding a New Eval Test

1. Create or edit a YAML file in `evals/`
2. Follow the existing format:
   ```yaml
   suite: my-custom-suite
   language: en
   description: "What this suite tests"

   tests:
     - name: "My test"
       input: "fix the login token refresh"
       mode: short
       asserts:
         - type: contains
           value: ["minimal", "auth"]
         - type: not_contains
           value: ["refactor"]
         - type: intent_match
           task_type: bugfix
           domain: auth
         - type: no_fences
         - type: not_empty
   ```
3. Run the new suite:
   ```bash
   promptfix eval --suite evals/my-custom-suite.yaml
   ```
4. Run the full suite to ensure no regressions:
   ```bash
   pytest -v
   promptfix eval --ci
   ```

### Adding a New Provider

1. Create a new file in `promptfix/providers/`
2. Inherit from `BaseProvider`
3. Implement `complete()`, `stream_complete()`, and `health_check()`
4. Add tests in `tests/test_providers.py`
5. Register in `promptfix/rewriter.py::create_provider()`

## Pull Request Process

1. **Create a feature branch**: `git checkout -b feature/my-feature`
2. **Make your changes** with clear commit messages
3. **Run tests**: `pytest -v` (must show 291+ passed)
4. **Run eval suite**: `promptfix eval --ci --threshold 75`
5. **Update documentation** if needed (README, docstrings)
6. **Submit a PR** with a clear description

## Reporting Issues

When reporting bugs, please include:
- Python version
- OS and version
- Steps to reproduce
- Expected vs actual behavior
- Error messages or logs

## Community

- Be respectful and constructive
- Help others in issues and discussions
- Share your use cases and feedback

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
