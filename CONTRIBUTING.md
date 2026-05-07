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

All 152+ tests must pass before submitting a PR.

### Running the Evaluation Suite

```bash
promptfix eval --ci
```

The CI threshold is 75/100. Ensure your changes don't drop the evaluation score.

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
   tests:
     - name: "My test"
       input: "..."
       mode: short
       asserts:
         - type: contains
           value: ["expected"]
   ```
3. Run `promptfix eval` to verify

### Adding a New Provider

1. Create a new file in `promptfix/providers/`
2. Inherit from `BaseProvider`
3. Implement `complete()`, `stream_complete()`, and `health_check()`
4. Add tests in `tests/test_providers.py`
5. Register in `promptfix/rewriter.py::create_provider()`

## Pull Request Process

1. **Create a feature branch**: `git checkout -b feature/my-feature`
2. **Make your changes** with clear commit messages
3. **Run tests**: `pytest -v`
4. **Run eval suite**: `promptfix eval --ci`
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
