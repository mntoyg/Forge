# Release Workflow

Releases are deliberate and cut by a human. Nothing here is automatic until a
tag exists.

## Versioning

[Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

While the project is `0.x`:

- `0.MINOR` increments may break the CLI contract.
- `0.x.PATCH` is bugfixes only.
- `1.0.0` waits until the command surface is one we intend to keep.

The version lives in exactly two places, and they must agree:

- `pyproject.toml` -> `project.version`
- `src/forge/__init__.py` -> `__version__`

`scripts/release.py` fails the release if they disagree, so there is no way to
ship a mismatched build by accident.

## PyPI Trusted Publishing setup

Before tagging a release, configure a pending Trusted Publisher in the PyPI
account that will own the package:

| PyPI field | Value |
| --- | --- |
| Project name | `mntoyg-forge` |
| Owner | `mntoyg` |
| Repository | `Forge` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

In GitHub repository settings, create the `pypi` environment. Add required
reviewers if the maintainers want a manual approval before publishing. The
workflow stores no PyPI API token; only its `pypi-publish` job receives
`id-token: write`. The PyPI publisher is pending until first use and does not
reserve the package name. If PyPI rejects `mntoyg-forge` during project
creation, stop and ask the owner to choose another name.

## Steps

### 1. Confirm `main` is green

CI must be passing on the commit you intend to tag. Do not tag a red commit
and plan to fix it after.

### 2. Update the version

Edit both files above to the new version.

### 3. Update the changelog

Move everything under `Unreleased` into a new dated section:

```markdown
## [0.1.0] - 2026-01-31

### Added
### Changed
### Fixed
```

Leave an empty `Unreleased` section behind.

### 4. Run the preflight

```bash
uv run python scripts/release.py 0.1.0
```

It checks the version in both files, the changelog section, the semantic
version format, and a clean working tree. It does not tag or push - that
remains a human action.

### 5. Commit

```bash
git commit -am "chore(release): 0.1.0"
git push origin main
```

### 6. Tag

```bash
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

The tag triggers `.github/workflows/release.yml`. It re-runs the quality gate,
builds one wheel and source archive, then sends that same artifact set to two
separate jobs: one creates the GitHub Release, and one publishes it to PyPI.
The GitHub Release job alone has `contents: write`; the PyPI job alone has
`id-token: write` and uses the dedicated `pypi` environment.

### 7. Verify

- The release workflow is green.
- The GitHub Release exists and has the built artifacts.
- The PyPI project exists and has the same files as the GitHub Release; compare
  SHA-256 checksums for every distribution file.
- The PyPI release shows trusted-publisher provenance.
- The release notes read correctly.

## If a release is broken

Do not delete or move a published tag. Fix forward:

1. Fix the bug on `main`.
2. Cut the next patch release.
3. Note the problem in the changelog entry for the new version.

## Install from PyPI

After a release is published, users can install Forge with:

```bash
uv tool install mntoyg-forge
forge --version
```

For updates, use `uv tool upgrade mntoyg-forge`. The Python import package and
console command remain named `forge`.
