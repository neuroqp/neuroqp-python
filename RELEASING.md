# Releasing NeuroQP Python

This is the maintainer runbook for publishing the Python package, GitHub
release, versioned documentation, and coding-agent skill.

## Release model

```text
source branch -> pull request -> main -> version tag
                                      |
                                      +-> PyPI package
                                      +-> GitHub release
                                      +-> docs-site branch -> Vercel
```

Vercel does not build or publish the Python package. GitHub Actions builds the
documentation and commits the generated static files to `docs-site`; Vercel
serves that branch.

## Versions

These versions are independent:

| Version | Example | Meaning |
| --- | --- | --- |
| Package | `0.1.0` | NeuroQP Python release on PyPI |
| Documentation | `0.1` | Mike documentation slot for the latest `0.1.x` release |
| Export format | `v2` | NeuroQP project-export format understood by the SDK |

Normal pull requests do not change the package version. During development,
`main` uses the next `.dev0` version.

## Branches and workflows

| Ref | Purpose | Automation |
| --- | --- | --- |
| Feature or Dependabot branch | Proposed source change | CI and CodeQL on the pull request |
| `main` | Reviewed source and the next development version | CI and CodeQL; compatible skill changes may update `docs-site` |
| `release/<version>` | Version and changelog changes for one release | Normal pull-request checks |
| `v<version>` tag | Explicit publication authorization | Package build, attestation, PyPI, GitHub release, and versioned docs |
| `docs-site` | Generated static site; never edit manually | Vercel production deployment |

The release tag is pushed manually after the release pull request is merged.
Merging the pull request does not publish the package.

## One-time external configuration

### GitHub

- Protect `main`: require a pull request and current CI and CodeQL checks.
- Prevent force pushes and branch deletion.
- Keep the `pypi` environment. Its deployment must require maintainer approval.

### PyPI

Configure a Trusted Publisher with:

- Owner: `neuroqp`
- Repository: `neuroqp-python`
- Workflow: `release.yml`
- Environment: `pypi`

Enable two-factor authentication and add a backup project owner. GitHub uses
OIDC for publication; do not create or store a PyPI API token in GitHub.

### Vercel

Configure the `neuroqp-python` project under Renaissance AI Projects:

- Repository: `neuroqp/neuroqp-python`
- Production branch: `docs-site`
- Preview branch tracking: off
- Framework preset: `Other`
- Root directory: `.`
- Build, install, and output-directory overrides: blank

Vercel serves the already-generated static branch, so no Vercel credential is
stored in GitHub. Attach `python.neuroqp.com` only after the first PyPI release
and the stable `neuroqp-python.vercel.app` deployment have both been verified.

## Prepare a release

Set the intended version, for example:

```bash
VERSION=0.1.0
```

Start from current `main`:

```bash
git switch main
git pull --ff-only
git switch -c "release/$VERSION"
```

Change only:

1. `pyproject.toml`: set `[project].version`.
2. `src/neuroqp/__init__.py`: set `__version__`.
3. `uv.lock`: refresh the local `neuroqp` package metadata with `uv lock`.
4. `CHANGELOG.md`: replace `Unreleased` with the release date.

Review the lockfile diff and reject unrelated dependency updates.

Run the complete preflight:

```bash
uv sync --locked --group dev --group docs
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run tox
uv run python scripts/build_example_export.py --check
uv run mkdocs build --strict
uv build
git diff --check
```

Also execute the notebooks, clean-install the built wheel with pip and uv, test
the bundled skill, and repeat the private real-export smoke test.

Open a pull request, require all checks to pass, update it to current `main`,
and squash-merge it. Confirm the merge commit contains the intended stable
version before proceeding.

## Publish

Publication is a separate, explicit action:

```bash
git switch main
git pull --ff-only
git tag -a "v$VERSION" -m "NeuroQP Python $VERSION"
git push origin "v$VERSION"
```

The tag starts `.github/workflows/release.yml`, which:

1. Refuses development versions and mismatched tags.
2. Runs the checks and builds the wheel and source distribution.
3. Attests the distributions.
4. Publishes them to PyPI through Trusted Publishing.
5. Creates the GitHub release and attaches the distributions.
6. Publishes the minor documentation slot and `latest` alias to `docs-site`.
7. Publishes root AI-readable documentation and the versioned skill bundle.

## Verify

- Install the published package with pip and uv on Python 3.12–3.14.
- Verify `neuroqp.__version__`, the CLI, API, TIFF handling, notebooks, and
  skill installation.
- Verify the GitHub release contains the wheel and source distribution.
- Verify PyPI shows the release and provenance.
- Verify `docs-site` advanced and Vercel deployed that exact commit.
- Check the version selector, search, themes, downloads, `llms.txt`,
  `llms-full.txt`, rendered Markdown, and skill endpoints.
- For the first release, attach and verify `python.neuroqp.com` last.

PyPI releases are immutable. Never reuse a published version or move its tag.
If publication partially succeeds, inspect the workflow before retrying; use a
new patch version when PyPI already contains the release.
