# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

Categories: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

## [Unreleased]

### Added

- Repository foundation: Clean Architecture layer skeleton under `src/forge/`,
  with each layer documenting its own dependency rules.
- `forge` console entry point with `--version`, and help on a bare invocation.
- Toolchain configuration in `pyproject.toml`: uv, Black, Ruff, mypy in strict
  mode, pytest with `unit` / `integration` / `e2e` markers.
- Mechanical enforcement of the dependency direction: Ruff `TID251` bans
  framework imports outside their permitted layers, and a unit test parses
  every source file under `domain/` and `application/` to assert no forbidden
  package is imported.
- Test scaffold with a fixture that strips ambient `FORGE_*` variables so tests
  cannot depend on a developer's local configuration.
- CI workflow running format, lint, type, and test checks on every pull
  request; release workflow triggered by a `v*.*.*` tag.
- Developer scripts: `scripts/setup.py`, `scripts/check.py`,
  `scripts/release.py`.
- Product documentation: vision, requirements with stable IDs, roadmap.
- Architecture documentation: overview, components, data flow.
- ADR-0001 (Python), ADR-0002 (Clean Architecture), ADR-0003 (AI provider
  abstraction), ADR-0004 (Typer), ADR-0005 (uv).
- Development documentation: setup, coding standard, testing, git workflow.
- AI agent collaboration model under `.forge/`: agent roles, the source of
  truth hierarchy, six workflows, five reusable prompts, and four shared
  context files.
- Issue templates, a pull request template, `.env.example`, and an example
  input file.
- `.gitattributes` pinning line endings to LF in the repository and the working
  tree, so a commit's line endings no longer depend on the contributor's
  `core.autocrlf` setting.

### Security

- `.env` is git-ignored and `.env.example` ships only empty placeholders.
- Documented security principles for handling secrets, file paths, command
  execution, and untrusted repository and model content.

---

## Release history

No releases yet. The first will be `0.1.0`, when `forge debug` is implemented -
see [ROADMAP.md](ROADMAP.md).

<!--
Template for a release section - replace X.Y.Z with the real version:

  ## [X.Y.Z] - YYYY-MM-DD

  ### Added
  ### Changed
  ### Fixed
-->
