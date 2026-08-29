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

The tag triggers `.github/workflows/release.yml`, which re-runs the full
quality gate, builds the distribution with `uv build`, and creates a GitHub
Release with the artifacts attached.

### 7. Verify

- The release workflow is green.
- The GitHub Release exists and has the built artifacts.
- The release notes read correctly.

## If a release is broken

Do not delete or move a published tag. Fix forward:

1. Fix the bug on `main`.
2. Cut the next patch release.
3. Note the problem in the changelog entry for the new version.

## Not in scope yet

Publishing to PyPI. Forge has no user-facing capability yet, so there is
nothing worth installing from an index. Adding it is an architecture change and
needs its own decision and its own trusted-publishing setup.
