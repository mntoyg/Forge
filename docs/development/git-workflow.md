# Git Workflow

## Branching model

`main` is the shared working branch. Commit each completed, checked change
directly to `main` and push it to `origin/main` after reviewing the diff.

```text
main -> checked commit -> origin/main
```

Branch names:

```text
feat/<short-slug>       a new capability
fix/<short-slug>        a bug fix
refactor/<short-slug>   behaviour-preserving restructure
test/<short-slug>       tests only
docs/<short-slug>       documentation only
chore/<short-slug>      tooling, dependencies, CI
```

Pull the latest `main` with `git pull --ff-only` before starting work. Do not
create a branch for routine changes.

```bash
git switch main
git pull
git pull --ff-only
```

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <imperative summary>

<body: why, not what>

<footer: Closes #123 / BREAKING CHANGE: ...>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `build`,
`perf`, `style`.

The scope is the area touched - usually the layer or the feature:

```text
feat(debug): add source file analyzer
fix(cli): handle missing file
refactor(ai): isolate provider adapter
test(debug): add analyzer tests
docs: update architecture documentation
chore(deps): bump ruff to 0.9.2
```

Rules for the subject line:

- Imperative mood: "add", not "added" or "adds".
- Lowercase after the colon; no trailing period.
- 72 characters or fewer.
- Describe the change, not the file list.

Write a body whenever the subject is not self-explanatory - always, for a bug
fix:

```text
fix(cli): handle missing file

Reading a path that does not exist raised an unhandled OSError and printed a
traceback. It now reports the path and exits with code 2.

Closes #42
```

## What belongs in one commit

One logical change. A rename and a behaviour change are two commits. A
formatting pass is its own commit, never mixed with logic.

Each commit should build and pass its own tests. That is what makes `git
bisect` useful when something breaks in three months.

## Checks before pushing

Before committing and pushing:

```bash
uv run python scripts/check.py
```

Then:

1. Self-review the whole diff first. Most review comments are things the author
   would have caught by reading their own change once.
2. Link the requirement ID it satisfies in the commit body when relevant.
3. Commit to `main` and push to `origin/main`.

### Review expectations

- Review the diff before pushing. Request a second review for high-risk changes
  when practical.
- CI must pass after a push; fix any failure promptly with a new commit.
- An architectural change references its accepted ADR.

An AI agent may perform a review pass. The author remains responsible for the
change and for resolving CI failures.

### CI requirements

Every pull request runs, and must pass:

| Check | Command |
| --- | --- |
| Format | `uv run black --check .` |
| Lint | `uv run ruff check .` |
| Types | `uv run mypy` |
| Tests | `uv run pytest` |

These are the same four `scripts/check.py` runs locally, in the same order, so
local and CI results cannot drift.

### Shared history

- Never force-push to `main` or rewrite shared history.
- If a push is rejected by branch protection, stop and report it. Do not
  disable or bypass the protection.
- Keep each commit logically focused and use Conventional Commit messages.
- Never commit `.env`, a key, a token, or anything git-ignored.

If a secret is ever committed: **treat it as compromised and rotate it
immediately.** Removing it from history is necessary but not sufficient - it
already exists in every clone.

## Releases

Tag-driven, and cut by a human. See `.forge/workflows/release.md`.

```bash
uv run python scripts/release.py 0.1.0   # preflight only, changes nothing
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```
