# Release guide

Package publication and documentation deployment happen only from a final release tag after a dedicated release PR changes `0.1.0.dev0` to a stable version.

## One-time external setup

1. Protect `main`; require pull requests and all CI jobs.
2. Enable GitHub Discussions, private vulnerability reporting, Dependabot alerts, secret scanning, push protection, and CodeQL default setup or the repository workflow.
3. Create the PyPI project and a trusted publisher for the GitHub `pypi` environment and `release.yml`.
4. Configure Vercel to deploy the `docs-site` branch as a static site with the repository root as its output directory and no build command.
5. Add the resulting documentation URL to `README.md` and the package’s project URLs.

## Release flow

1. Create a release PR that changes the version to `X.Y.Z`, updates the changelog, and completes the [release checklist](RELEASE_CHECKLIST.md).
2. Merge the release PR after all checks and manual smoke tests pass.
3. Create and push the signed tag `vX.Y.Z`.
4. The release workflow verifies that the tag and package version match and rejects development versions.
5. The workflow builds wheel and sdist artifacts, attests them, publishes through PyPI Trusted Publishing, creates the GitHub Release, updates the `support:X.Y` label, and deploys mike’s `X.Y` plus `latest` aliases to `docs-site`.

Never rewrite a released documentation snapshot. Correct documentation in a new package release.
