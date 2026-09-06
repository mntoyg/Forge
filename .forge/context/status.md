# Where the project is right now

> **The handover file.** Every other document describes what Forge *is*. This
> one describes what is *true today* - what works, what is next, what is
> blocked, and what would otherwise be rediscovered the hard way.
>
> Read it after `project.md` and before starting any task.

**Last verified:** 2026-09-06 on `main`, CI green on all three platforms.
Version `0.1.0` is prepared and unreleased: the tag is a human action. The
repository was recreated on this date - see below.

---

## Where we are

`forge debug <file>` works and has been run against a live model. `--diff`
narrows a run to the lines you have changed since the last commit, and has also
been run live. A finding that cites a line now carries what git knows about
that line - who last changed it, when, and how much the file has been moving.

Phases 0 to 2 of `docs/product/roadmap.md` are complete. Phase 3 has one item
left, and it is the one that was deferred on purpose - see below.

## What is true right now

Facts, each with how it was checked. Do not trust a line here that has no
verification - correct it or delete it instead.

| Fact | How it was verified |
| --- | --- |
| 356 pass locally with 1 skipped | `uv run pytest`. The skipped one is a symlink test Windows cannot run |
| `forge debug` finds the defects a file is known to have | Live, gpt-4o-mini: 3 of 3 in `examples/buggy_division.py` (617 in / 236 out), 4 of 4 in `examples/retry_backoff.js` (846 in / 354 out) |
| A file with no defects returns none | Live: `examples/safe_statistics.py`, 987 in / **8 out**. The whole reply was an empty list |
| Nothing in Forge is Python-specific | The `.js` run above. It sends text and reads a reply; the language is the model's problem |
| A whole-file run above 4,000 tokens says the answer may be partial | ADR-0012. `--diff` stays silent, because it is measured reliable |
| `--diff` is not affected by that, and is the strongest mode on a long file | Live: the same defect found at line 877 (3 of 3) and at line 3,807 (44,409 in), where a whole-file run misses it every time. ADR-0012 |
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

1. **Tag `v0.1.0`.** The version, the changelog section, and the preflight are
   done and on `main`; `.forge/workflows/release.md` step 6 is the tag, and it
   is deliberately a human action.
2. **Publish the repository, or stop calling it open-source.** It is private,
   while the README, `pyproject.toml` and the vision all say otherwise and the
   README tells a reader to clone a URL they cannot reach. The decision is a
   human's; the repository is ready for either answer.
3. **Review a whole file as a series of marked windows.** Measured, not
   guessed: marking lines carries attention and instruction does not, so the
   fix for the whole-file review is the mechanism `--diff` already uses, run
   over the file in turn. It still multiplies provider calls, so it needs the
   same decision the sweep is waiting on.
4. **Decide about the repository-wide sweep** - `forge debug --diff` with no
   file, the last Phase 3 item. Deferred deliberately: one provider call per
   changed file multiplies cost, and that deserves its own decision rather
   than arriving as a silent consequence of ADR-0008.

## Blocked, or needs a human

- **Nothing is blocked right now.**
- A live provider run costs the user money and needs their key. Do not run
  `forge debug` against a real provider without being asked.
- Merging is a human decision. Agents open pull requests; a person approves.

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
- **A long file is reviewed from the top until the model loses interest.**
  Not a size limit being hit - the identical defect at line 6 of an 877-line
  file is found, and missed at the end of the same file. Anything measuring
  quality must vary *where* the defect is, not only how big the file is.
- **Temperature 0 is not determinism.** Two runs over one unchanged file
  disagreed on how many findings there were and on which lines they sat.
  Anything that needs a repeatable answer needs caching, not a temperature.
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
- Update it in the same pull request as the work it describes.
- **A test enforces a 150-line budget.** If it fails, remove what is stale
  rather than raising the number. A sibling project grew a 13,000-line progress
  log that no agent could read without exhausting its context window, which
  made it worse than having no notes at all.
