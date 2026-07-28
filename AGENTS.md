# AGENTS.md

- Read `docs/specifications/export-v2.md` before changing export parsing,
  validation, models, or fixtures. The live NeuroQP exporter remains the
  ultimate source of truth if code and documentation disagree.
- Use `uv sync --all-groups` to install. Run Ruff, strict mypy, and pytest
  before pushing; use `uv run tox` for the supported Python matrix.
- Preserve backward compatibility for the public API and every published export
  format. Wire-format adapters stay private.
- Treat exports as untrusted input: never enable pickle loading, weaken archive
  path checks, or commit private real exports.
- Normal changes do not alter the package version or publish artifacts. Only a
  dedicated release PR may authorize publication.
