# Where the project is right now

> **The handover file.** Every other document describes what Forge *is*. This
> one describes what is *true today* - what works, what is next, what is
> blocked, and what would otherwise be rediscovered the hard way.
>
> Read it after `project.md` and before starting any task.

**Last verified:** 2026-08-31, on branch `feat/diff-analysis`.

---

## Where we are

`forge debug <file>` works and has been run against a live model. `--diff`
narrows a run to the lines you have changed since the last commit, and has also
been run live.

Phases 0 to 2 of `docs/product/roadmap.md` are complete. Phase 3 is partly
done: the `RepositoryInspector` port, the GitPython adapter, and `--diff` for a
single named file all exist. Two Phase 3 items remain - see below.

## What is true right now

Facts, each with how it was checked. Do not trust a line here that has no
verification - correct it or delete it instead.

| Fact | How it was verified |
| --- | --- |
| 296 pass locally with 1 skipped; 297 pass on CI | `uv run pytest`. The skipped one is a symlink test Windows cannot run |
| `forge debug` works against a live model | Run against `examples/buggy_division.py`, gpt-4o-mini |
| `forge debug --diff` reports only changed lines | Appended a bug to a file with two known older bugs; only the new one was reported |
| `--diff` costs *more* input, less output | 775 in / 88 out, against 660 in / 235 out for the same file whole. ADR-0008 says the saving is focus, not price |
| An untracked file counts entirely as new | Real repository test; `git diff` alone reports nothing for one |
| The model returns parseable JSON | Held on every live run so far. ADR-0007 stands |
| No provider SDK or git import outside `infrastructure/` | Ruff `TID251` plus `tests/unit/test_package.py` |
| No secret is committed | `.env` git-ignored; `.env.example` ships empty values |

## What to do next

In order. The reasoning matters more than the list - if you disagree with the
order, say why rather than silently reordering.

1. **Finish Phase 3.** Two items remain, and they are not equal. *Blame and
   recent-history context* is the useful one: knowing a line changed three
   times last week is real signal about risk. *Sweeping every changed file in
   one run* was deferred on purpose, because one provider call per file
   multiplies cost, and that needs its own decision rather than arriving as a
   silent consequence of ADR-0008.
2. **More real-model evidence before `0.1.0`.** Every live run so far has been
   one small Python file. Try a large file, another language, and - most
   importantly - **a file with no defects at all**, because a model asked to
   find problems will find them whether they exist or not.
3. **Decide about `httpx`.** Still a declared runtime dependency that nothing
   imports. Phase 3 used GitPython, not HTTP, so the "we will need it soon"
   argument is weaker than it was. Removing it needs an ADR; so does keeping
   it. The drift is what is not acceptable.

## Blocked, or needs a human

- **Nothing is blocked right now.**
- A live provider run costs the user money and needs their key. Do not run
  `forge debug` against a real provider without being asked.
- Merging is a human decision. Agents open pull requests; a person approves.

## Things that would otherwise be rediscovered the hard way

Each of these cost real time once. They are here so it happens only once.

- **`git diff` says nothing about an untracked file.** A file the user just
  wrote would look unchanged - the worst possible answer from the command that
  exists to review new work. `repository.py` special-cases it.
- **The OpenAI SDK (v3) vendors its own httpx as `httpx2`.** The `httpx` in
  `pyproject.toml` is a *different package*. A client passed to the SDK must be
  an `httpx2` client - see `tests/integration/test_openai_provider.py`.
- **A present-but-empty env var is `""`, not `None`.** This shipped as a bug:
  `FORGE_BASE_URL=` from `.env.example` reached the SDK as a real base URL and
  broke every request. Any new optional string setting needs the same guard.
- **`Path.write_text` writes CRLF on Windows.** Tests that care about content
  must use `write_bytes`. The reader normalises line endings so the same file
  produces the same prompt everywhere.
- **Creating a symlink on Windows needs elevation.** The workspace-escape test
  skips locally and runs on CI. A local green run does not cover it.
- **Never assert on rendered Rich output.** It wraps to the terminal width, so
  a test that reads `result.stdout` for a flag name passes on a wide terminal
  and fails on CI's 80 columns. Assert on the source string - `debug_cli.HELP`
  - and keep one test that the text reaches the user at all.
- **`forge debug` on a clean file still exits 0.** ADR-0006, deliberate. Do not
  "fix" it.

## How to keep this file useful

This file describes the **present**. It is not a log.

- History belongs in `git log` and `CHANGELOG.md`. Do not append to this file.
- When something here stops being true, **delete or rewrite the line**. Do not
  add a note saying it changed.
- Update it in the same pull request as the work it describes.
- **A test enforces a 150-line budget.** If it fails, remove what is stale
  rather than raising the number. A sibling project grew a 13,000-line progress
  log that no agent could read without exhausting its context window, which
  made it worse than having no notes at all.
