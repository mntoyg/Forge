# Where the project is right now

> **The handover file.** Every other document describes what Forge *is*. This
> one describes what is *true today* - what works, what is next, what is
> blocked, and what would otherwise be rediscovered the hard way.
>
> Read it after `project.md` and before starting any task.

**Last verified:** 2026-11-05 on `main`; FR-4.4 debug/inspect JSON and explain Stages A/B1/B2 are gate-verified.
Version `0.1.0` is published on GitHub Releases and PyPI. The owner verified
installation with `uvx --from mntoyg-forge==0.1.0 forge --version` (`forge 0.1.0`).
The repository was recreated on 2026-09-06 - see below.

---

## Where we are

`forge debug <file>` works and has been run against a live model. `--diff`
narrows a run to the lines you have changed since the last commit, and has also
been run live. A finding that cites a line now carries what git knows about
that line - who last changed it, when, and how much the file has been moving.

Phases 0 to 2 of `docs/product/roadmap.md` are complete. Phase 3 retains its
deferred repository-wide `debug --diff` sweep. Separately, `forge review` is
implemented under FR-6 and ADR-0014: it previews a bounded change set, asks
for TTY confirmation, and makes at most one provider call. It remains an AI
opinion and reports omissions and incomplete coverage.
`forge explain <FILE>` implements FR-7: it submits one bounded source snapshot
in at most one provider call and renders only claims with validated evidence.
Distribution decision: keep GitHub Releases and add PyPI through Trusted
Publishing (ADR-0017). Metadata and release workflow now use `mntoyg-forge`;
the workflow builds once and publishes the same artifacts to both channels.
The `v0.1.0` release workflow completed successfully, and the owner confirmed
the published CLI installs and runs from PyPI.

## What is true right now

Facts, each with how it was checked. Do not trust a line here that has no
verification - correct it or delete it instead.

| Fact | How it was verified |
| --- | --- |
| Local gate: 595 passed, 1 skipped; Black, Ruff, and mypy pass | `uv run python scripts/check.py`, 2026-11-05; Windows symlink test skips locally |
| `forge inspect [directory]` reports bounded local evidence; Git global excludes are outside its scan | Unit, integration, and CLI tests; full gate passes |
| `forge explain --help` renders provider disclosure and `--format text|json` | Real CLI subprocess test normalizes ANSI styling; full local gate passes |
| FR-4.4 JSON for debug/inspect/explain is complete; explain has safe path preflight and unchanged exit mapping | ADR-0019/0020; serializer unit and fake-provider CLI e2e tests; full gate |
| `forge review` bounds current and Git-base data before reads and maps changed lines from the source snapshot plus its Git base blob, without rereading the working tree | Integration tests cover byte limits, staged/unstaged changes, renames, changed/grown files, and zero provider calls on mismatch |
| `forge explain` requires every Purpose claim to have a locally valid call anchor exactly matching a validated Main flow call; invalid evidence retains its specific diagnostic | Deterministic parser, integration, and CLI tests; `uv run python scripts/check.py`, 2026-11-04 |
| `forge explain` drops recognized coordinated symbol actions when evidence has too few distinct `(kind, target)` anchors; distinct targets may share a line, repeated targets count once, and structural checks do not prove semantic entailment | Parser and fake-provider integration tests; full quality gate |
| `mntoyg-forge==0.1.0` installs from PyPI and runs as `forge 0.1.0` | Owner ran `uvx --from mntoyg-forge==0.1.0 forge --version`; release workflow run 41933271391 passed build, PyPI publish, and GitHub Release jobs |
| Latest approved live `forge explain` result omitted Purpose for an invalid target; the compound symbol claim with one reader anchor is now guarded by a deterministic parser check | Owner-approved call on 2026-11-05; no live call in this change |
| Setup instructions state which commands need an API key | `docs/development/setup.md` links to the provider setup in `docs/guides/getting-started.md` |
| `forge debug` finds the defects a file is known to have | Live, gpt-4o-mini: 3 of 3 in `examples/buggy_division.py` (617 in / 236 out), 4 of 4 in `examples/retry_backoff.js` (846 in / 354 out) |
| A file with no defects returns none | Live: `examples/safe_statistics.py`, 987 in / **8 out**. The whole reply was an empty list |
| A whole-file run above 4,000 tokens says the answer may be partial | ADR-0012. `--diff` stays silent, because it is measured reliable |
| `--diff` is not affected by that, and is the strongest mode on a long file | Live: the same defect found at line 877 (3 of 3) and at line 3,807 (44,409 in), where a whole-file run misses it every time. ADR-0012 |
| Marking only works for a small region | Live, 3,806-line file: 8 marked lines found the defect; 300 and 800 marked lines missed it on the window's last line, twice each. ADR-0013 |
| A defect at the end of a long file is not reported | Live, gpt-4o-mini, one injected division at the end: found at 334 lines (3,927 in), missed at 877, 1,922 and 3,807 - and at once when moved to line 6 of that same file. Three prompt variants telling it to read to the end all failed: marking works, wording does not |
| The same file can answer differently twice | Live, same file at temperature 0, identical 846-token prompt: 4 findings (354 out), then 3 (288 out), citing different lines. Temperature 0 is not determinism |
| `forge debug --diff` reports only changed lines | Appended a bug to a file with two known older bugs; only the new one was reported |
| `--diff` costs *more* input, less output | 775 in / 88 out, against 660 in / 235 out for the same file whole. ADR-0008 says the saving is focus, not price |
| An untracked file counts entirely as new | Real repository test; `git diff` alone reports nothing for one |
| A located finding says who last changed its line, and when | Integration tests against real repositories built in a temporary directory |
| History never reaches the provider | It is looked up from the parsed findings, after the response. ADR-0009, and `tests/unit/test_analyze.py` |
| No repository means no history and no failure | Every `RepositoryError` from that lookup becomes "no history" |
| The model returns parseable JSON | Held on every live run so far. ADR-0007 stands |
| No provider SDK or git import outside `infrastructure/` | Ruff `TID251` plus `tests/unit/test_package.py` |
| Every declared dependency is imported by something | ADR-0010 removed the one that was not. `uv run python -c "import httpx"` fails, and nothing needs it to |
| No secret is committed | `.env` git-ignored; `.env.example` ships empty values |

## What to do next

In order. The reasoning matters more than the list - if you disagree with the
order, say why rather than silently reordering.

1. **Review remaining `forge explain` quality limits.** Coordinated symbol
   claims with too few unique `(kind, target)` anchors are omitted; counts do
   not prove semantic support. Latest live output omitted Purpose for an
   invalid target. Provider evaluation needs owner approval.
2. **Re-decide long-file review.** ADR-0013 is suspended; run the attention
   measurement and accept a new ADR before implementation.

## Blocked, or needs a human

- AI usage cap: at most 14 percentage points of the weekly plan per local day.
  Latest meter: 24% over 7 days; daily use is unavailable.
- `mntoyg/Forge` is public; `mntoyg/Forge-archive` remains private.
- A live provider run costs the user money and needs their key. Do not run
  `forge debug` against a real provider without being asked.
- Never force-push or bypass GitHub branch protection.

## Things that would otherwise be rediscovered the hard way

Each of these cost real time once. They are here so it happens only once.

- **This repository was recreated on 2026-09-06 and `mntoyg/Forge-archive` must
  stay private.** Rewriting `main` would have cleaned 5 commits and left 24 more
  carrying a personal email inside merged pull requests, which GitHub keeps
  forever - readable by anyone through a PR's Commits tab. The archive holds
  that history and pull requests #1 to #15; this repository holds the same code
  with the address rewritten. Audit both places before publishing anything.
- **`git diff` says nothing about an untracked file.** A file the user just
  wrote would look unchanged - the worst possible answer from the command that
  exists to review new work. `repository.py` special-cases it.
- **A git-ignored file is not in `untracked_files`.** git leaves it out of
  that list entirely, so a check for "untracked" says tracked, and `git blame`
  then fails on a path git has never heard of. Generated code, vendored
  dependencies, and anything inside a virtualenv are all ordinary things to
  point `forge debug` at. Found by running it on a file under `.venv/`.
- **Blame the working tree, not `HEAD`.** One uncommitted insertion shifts
  every line below it, so blaming `HEAD` annotates the wrong lines on exactly
  the file this is most often run on. `git blame` with no revision is right.
- **`git blame --porcelain` omits the headers of a commit it has already
  described.** Parsing it means keeping a cache, and the cache is where the bug
  will be. `--line-porcelain` repeats every block; use that.
- **The OpenAI SDK (v3) vendors its own httpx as `httpx2`.** It is a different
  package from `httpx`, which Forge no longer declares at all (ADR-0010). A
  client passed to the SDK must be an `httpx2` client - see
  `tests/integration/test_openai_provider.py`.
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
- **A file that documents its own defects can pull the model's line numbers
  into the comment describing them**, as `examples/retry_backoff.js` did once.
  Every file in `examples/` has such a header; real user code does not.
- **`forge debug` on a clean file still exits 0.** ADR-0006, deliberate. Do not
  "fix" it.

## How to keep this file useful

This file describes the **present**. It is not a log.

- History belongs in `git log` and `CHANGELOG.md`. Do not append to this file.
- When something here stops being true, **delete or rewrite the line**. Do not
  add a note saying it changed.
- Update it in the same commit as the work it describes.
- **A test enforces a 150-line budget.** If it fails, remove what is stale
  rather than raising the number. A sibling project grew a 13,000-line progress
  log that no agent could read without exhausting its context window, which
  made it worse than having no notes at all.
