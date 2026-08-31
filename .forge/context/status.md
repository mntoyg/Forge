# Where the project is right now

> **The handover file.** Every other document describes what Forge *is*. This
> one describes what is *true today* - what works, what is next, what is
> blocked, and what would otherwise be rediscovered the hard way.
>
> Read it after `project.md` and before starting any task.

**Last verified:** 2026-08-31, at commit `452d1d6` on `main`.

---

## Where we are

Forge has its first working capability. `forge debug <file>` reads a source
file, sends it to an OpenAI-compatible provider, and prints findings. It has
been run against a live model and works end to end.

Phases 0, 1, and 2 of `docs/product/roadmap.md` are complete. Phase 3
(repository awareness) has not been started - no design, no ADR, no code.

## What is true right now

Facts, each with how it was checked. Do not trust a line here that has no
verification - correct it or delete it instead.

| Fact | How it was verified |
| --- | --- |
| `main` is at `452d1d6`, CI green | `gh run list --branch main` |
| 257 tests pass locally, 258 on CI | `uv run pytest`; the extra one is a symlink test that Windows skips |
| `forge --version` works with no key at all | Run; config loads per command, not at import |
| `forge debug` works against a live model | Run twice against `examples/buggy_division.py`, gpt-4o-mini, ~617 in / ~230 out tokens |
| The model returned parseable JSON both times | ADR-0007's assumption held; no fallback needed yet |
| No provider SDK is imported outside `infrastructure/` | Ruff `TID251` plus `tests/unit/test_package.py` |
| No secret is committed | `.env` is git-ignored; `.env.example` ships empty values |

## What to do next

In order. The reasoning matters more than the list - if you disagree with the
order, say why rather than silently reordering.

1. **Phase 3: repository awareness.** A `RepositoryInspector` port over
   GitPython; `forge debug --diff` to analyse a change rather than a whole
   file; defined behaviour outside a git repository. Needs a design and
   probably an ADR before any code - see `.forge/workflows/feature.md`.
2. **More real-model evidence.** Two successful runs against one small Python
   file is thin. Before `0.1.0`, try larger files, other languages, and a file
   with no defects at all - the last one matters most, because a model asked
   to find problems will find them whether they exist or not.
3. **Decide about `httpx`.** It is a declared runtime dependency that nothing
   imports. Removing it needs an ADR (`.forge/context/decisions.md`); so does
   keeping it on the grounds that Phase 3+ will use it. Either is fine; the
   drift is not.

## Blocked, or needs a human

- **Nothing is blocked right now.**
- A real provider run costs the user money and needs their key. An agent must
  not run `forge debug` against a live provider without being asked to.
- Merging to `main` is a human decision. Agents open pull requests; a person
  approves them.

## Things that would otherwise be rediscovered the hard way

Each of these cost real time once. They are here so it happens only once.

- **The OpenAI SDK (v3) vendors its own httpx as `httpx2`.** The `httpx` in
  `pyproject.toml` is a *different package*. A client passed to the SDK must be
  an `httpx2` client - see `tests/integration/test_openai_provider.py`.
- **A present-but-empty env var is `""`, not `None`.** This shipped as a bug:
  `FORGE_BASE_URL=` from `.env.example` reached the SDK as a real base URL and
  broke every request. Fixed in `452d1d6`. Any new optional string setting
  needs the same treatment.
- **`Path.write_text` writes CRLF on Windows.** Tests that care about content
  must use `write_bytes`. The reader normalises line endings so the same file
  produces the same prompt on every platform.
- **Ruff `N818` requires exception names to end in `Error`.** The names in
  ADR-0003 predate that and were renamed; the ADR text was corrected to match.
- **Creating a symlink on Windows needs elevation.** The workspace-escape test
  skips locally and runs on CI. Never assume a local green run covers it.
- **`forge debug` on a file with no findings still exits 0.** This is ADR-0006
  and is deliberate. Do not "fix" it.

## How to keep this file useful

This file describes the **present**. It is not a log.

- History belongs in `git log` and `CHANGELOG.md`. Do not append to this file.
- When something here stops being true, **delete or rewrite the line**. Do not
  add a note saying it changed.
- Update it in the same pull request as the work it describes, the way
  `CHANGELOG.md` is updated.
- **If this file passes roughly 150 lines, something in it belongs somewhere
  else.** A sibling project accumulated a 13,000-line progress log that no
  agent could read without exhausting its context window - which made it worse
  than having no notes at all. Length here is a defect, not thoroughness.
