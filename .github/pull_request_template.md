## What does this change do?

<!-- One or two sentences. Describe the change, not the diff. -->

## Why?

<!-- Link the issue, requirement, or ADR that motivates this.
     Closes #___ -->

## Type of change

- [ ] `feat` - new capability
- [ ] `fix` - bug fix
- [ ] `refactor` - behaviour-preserving restructure
- [ ] `test` - tests only
- [ ] `docs` - documentation only
- [ ] `chore` / `ci` / `build` - tooling

## Architecture

- [ ] The dependency direction is unchanged (presentation -> application -> domain).
- [ ] No framework or SDK import was added to `domain/` or `application/`.
- [ ] This change needs an ADR, and one is included (`docs/architecture/decisions/`).
- [ ] Not applicable - this change has no architectural impact.

## Checks

- [ ] `uv run python scripts/check.py` passes locally.
- [ ] New behaviour is covered by tests at the right level (unit / integration / e2e).
- [ ] Tests are deterministic and make no real AI provider calls.
- [ ] Documentation is updated where the change makes it stale.
- [ ] `CHANGELOG.md` has an entry under `Unreleased` (skip for `chore`/`ci`).

## Security

- [ ] No secret, API key, or token is committed or logged.
- [ ] Any new file path handling is validated against traversal outside the workspace.
- [ ] No new arbitrary command execution or unreviewed file modification.

## AI agent disclosure

<!-- Which agent, if any, produced this change? See .forge/agents/README.md. -->

- Authoring agent: <!-- e.g. Claude Code / Cursor / Aider / human -->
- [ ] A human reviewed the full diff before requesting review.
