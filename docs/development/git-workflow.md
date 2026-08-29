# Git Workflow

## Branching model

`main` is always releasable. Every change arrives through a pull request from a
short-lived branch.

```text
main
  |
  +-- feat/debug-source-reader
  +-- fix/missing-file-exit-code
  +-- docs/architecture-overview
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

Keep branches short-lived. A branch open for two weeks is a merge conflict
waiting to be discovered.

```bash
git switch main
git pull
git switch -c feat/debug-source-reader
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

## Pull requests

Before opening one:

```bash
uv run python scripts/check.py
```

Then:

1. Push the branch and open a pull request against `main`.
2. Fill in the template honestly, including the architecture and security
   sections.
3. Self-review the whole diff first. Most review comments are things the author
   would have caught by reading their own change once.
4. Link the issue and the requirement ID it satisfies.

### Review requirements

- At least one approving review from someone other than the author.
- Every conversation resolved - fixed, or answered with a reason.
- CI green. A red build is never merged, and never "fixed after merge".
- An architectural change references its accepted ADR.

An AI agent may perform the first review pass, but **a human approves**. An
agent produces findings; it does not approve a merge.

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

### Merging

Squash and merge. The squashed commit message follows Conventional Commits and
becomes the changelog source.

Delete the branch after merging.

## History rules

- **Never force-push to `main`.**
- Never rewrite history on a branch someone else is reviewing; add commits and
  squash on merge instead.
- Rebasing your own unshared branch onto `main` is fine and encouraged.
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
