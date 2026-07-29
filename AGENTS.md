# AGENTS.md

NeuroQP Python is the Python SDK and CLI for reading and validating NeuroQP project exports. This repository contains the public package, export models, validation, and tests.

## Development

- Sync: `uv sync`
- Test: `uv run pytest`
- Test all Python versions: `uv run tox`
- Lint: `uv run ruff check .`
- Type-check: `uv run mypy`

## Rules

- Read `docs/specifications/export-v2.md` before changing export parsing, models, or fixtures.
- Treat exports as untrusted input; never enable pickle loading or weaken archive path checks.
- Preserve backward compatibility for the public API and published export formats.
- Keep Python files at or below 500 lines.
- Read `RELEASING.md` before dedicated release work; normal changes never alter
  versions or publish artifacts.
