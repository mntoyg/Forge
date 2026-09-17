# ADR-0013 - Review a long file as a series of marked windows

## Status

Accepted - 2026-09-17: **Option A**, with `FORGE_MAX_REVIEW_CALLS`
defaulting to **8** (a file of about 2,400 lines at a 300-line window).
Not yet implemented; the window-size measurement below comes first.

## Context

ADR-0011 and ADR-0012 measured two things about gpt-4o-mini, and together they
say what the fix for a long file has to look like.

**An unmarked whole-file review stops reading.** One unguarded division,
appended as the last function of real files, is reported at 334 lines (3,927
input tokens) and missed at 877, 1,922 and 3,807 lines. Moved to line 6 of the
877-line file it is found at once.

**Marked lines are read wherever they sit.** The same defect, in the same file,
is found by `--diff` at line 877 (3 of 3) and at line 3,807 of a 44,409-token
prompt (1 of 1). Three general instructions to the whole-file review - read to
the last line, an end-of-file marker, and both - all failed.

So wording does not carry attention and marking does. The whole-file review is
still the default command, it still under-reports above ~4,000 tokens, and a
caveat is all that stands between that and a user trusting `no findings`.

## Options

**A. Whole file every call, a different window marked each time.** The
mechanism `--diff` already uses (ADR-0008), run over the file in turn: window
one marks lines 1-300, window two marks 301-600, and so on. Every call sees the
whole file, so a finding can use code anywhere in it, and line numbers stay
file line numbers - nothing is translated back.

**B. Split the file into overlapping chunks, each sent alone.** Far cheaper:
each call pays only for its chunk. It also reintroduces both objections ADR-0008
recorded against sending a diff: a chunk cannot see the callers and definitions
outside it, and its line numbers must be offset back to the file - arithmetic
that is a new place to produce a confidently wrong location.

**C. Chunks plus a whole-file outline** (signatures only) as shared context.
Between A and B on cost and context. No evidence either way, and the outline is
a second thing to build and get wrong.

**D. Keep the caveat and stop there.** The status quo.

Estimated input cost on gpt-4o-mini at about $0.15 per million input tokens,
using the two files already measured, with a 300-line window:

| file | calls | A: input tokens | A: cost | B: input tokens | B: cost |
| --- | --- | --- | --- | --- | --- |
| 877 lines / 10.2k | 3 | 30.6k | ~$0.005 | ~12k | ~$0.002 |
| 3,807 lines / 44.3k | 13 | 576k | ~$0.086 | ~53k | ~$0.008 |

A file under 4,000 tokens is unaffected by every option: it stays one call.

## Decision

**Option A**, because it is the only one with evidence behind it, and because it
reuses a mechanism and a line-number guarantee the project already relies on.

- **Only above the threshold.** A file under `RELIABLE_INPUT_TOKENS` is one
  call, exactly as today. Most files never pay anything extra.
- **A ceiling on calls per file** - `FORGE_MAX_REVIEW_CALLS`. Above it, Forge
  runs one whole-file call, keeps the ADR-0012 caveat, and says why it did not
  window the file. Cost can never grow silently with file size.
- **A finding belongs to the window that marked its line.** Each window's
  prompt scopes the answer to its marked lines, as `CHANGE_INSTRUCTION` does, so
  the same line is not reported by several windows and nothing needs fuzzy
  de-duplication. A finding citing an unmarked line is dropped - its own window
  will report it.
- **Findings with no line** are kept from the first window only. They describe
  the file, and every window would otherwise repeat them.
- **The caveat goes away for a windowed run**, because every line was marked.

## Measure before building

The window size is not known. The 4,000-token result is for an *unmarked*
review; `--diff` has only been measured marking eight lines. How many marked
lines a model attends to is a separate question, and one measurement answers
it: mark a window of 300 lines and one of 800, each with the defect on its last
line, at about 44,000 tokens. Two to four calls, one to three US cents.

## Consequences

**Easier:** the default command reviews the whole of a long file, the silent
failure is gone rather than labelled, and `--diff` and the windowed review share
one tested prompt path.

**Harder:** a long file costs several times more under A, bounded by the
ceiling; findings are merged from several responses, which is a new place for a
bug; and non-determinism now applies per window.

**Decided:** A over B, and a ceiling of 8 calls. **Still to settle, by
measurement rather than opinion:** the window size, which fixes how many lines
the ceiling of 8 actually covers.
