# Contributing

Thank you for contributing to NeuroQP Python.

## Before opening a pull request

- Use GitHub Discussions for questions and open an issue before starting a large or compatibility-sensitive change.
- Keep changes focused and preserve the public API and supported export formats.
- Never commit real project exports, patient information, credentials, or other private data.
- Add or update tests for behavior changes and documentation for user-visible changes.
- Run `uv sync`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`, and `uv run pytest`.

## Pull requests

External pull requests are welcome. Maintainers may decline speculative abstractions, new dependencies without a clear need, or features outside the package’s documented scope. By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

Security vulnerabilities must be reported privately through the process in [SECURITY.md](SECURITY.md), never through a public issue or pull request.
