# Internal release-candidate checklist

This checklist records reproducible phase 3 verification. Do not include private export names, paths, metadata, or results in commits.

## Automated checks

- [x] `uv lock --check`
- [x] `uv run ruff format --check .`
- [x] `uv run ruff check .`
- [x] `uv run mypy`
- [x] `uv run pytest`
- [x] `uv run tox`
- [x] `uv run --group docs python scripts/build_example_export.py --check`
- [x] `uv run --group docs mkdocs build --strict`
- [x] `uv build`

## Clean-install smoke test

- [x] Install the wheel in a clean environment.
- [x] Import `neuroqp` and verify its version.
- [x] Run `neuroqp --help`.
- [x] Validate and inspect the downloadable synthetic export.

## Private real-export smoke test

- [x] Open one fresh v2 export from NeuroQP.
- [x] Navigate animals, slices, stainings, registration, and classification metadata.
- [x] Load at least one classification result and one match result when present.
- [x] Record only pass/fail and the commands used; never commit private export content.

## External repository checks

- [ ] Required `main` protections and CI checks are enabled.
- [ ] Discussions and private vulnerability reporting are enabled.
- [ ] Dependabot, secret scanning, push protection, and CodeQL are enabled.
- [ ] PyPI Trusted Publishing is configured for the `pypi` environment.
- [ ] Vercel production deploys only the `docs-site` branch.

## Release boundary

- [x] The candidate remains `0.1.0.dev0`.
- [x] PyPI contains no NeuroQP Python release from this phase.
- [ ] The release-candidate PR is reviewed before it is squash-merged to `main`.
