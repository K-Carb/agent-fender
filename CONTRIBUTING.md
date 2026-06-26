# Contributing to agent-fender

## Setup

```bash
git clone https://github.com/Carb/agent-fender.git
cd agent-fender
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v
```

106 tests should pass in under 2 seconds.

## What to Work On

- **Good first issues**: Look for issues tagged `good first issue`
- **Feature requests**: Open an issue first to discuss before implementing
- **Bug fixes**: PRs welcome with a test that reproduces the bug

## Principles

- **Zero dependencies is sacred.** Do not add third-party packages.
- **Pure functions over stateful objects.** Every component should be independently testable.
- **Result dataclasses over exceptions.** The caller should never catch exceptions from this library.
- **Tests for everything.** Every guard, every edge case, every error path.

## Pull Request Process

1. Fork the repo
2. Create a feature branch
3. Add tests for your changes
4. Ensure all tests pass (`pytest tests/ -v`)
5. Open a PR against `main`
