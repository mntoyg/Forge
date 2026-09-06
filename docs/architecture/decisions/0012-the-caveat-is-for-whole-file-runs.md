# ADR-0012 - The partial-result caveat is for whole-file runs only

## Status

Accepted - 2026-09-06

Supersedes [ADR-0011](0011-warn-when-a-result-may-be-partial.md), which held for
a few hours and was measured wrong on one point.

## Context

ADR-0011 shipped a caveat above 4,000 input tokens, on the measurement that a
defect at the end of a long file goes unreported. That measurement stands. What
it did not test was whether **`--diff` shares the problem**, and the assumption
that it did was never stated - it was simply inherited, because `--diff` sends
the whole file too (ADR-0008).

It does not share the problem. Same file on disk, same model, same token count,
only the prompt differs:

| review | 877 lines / ~10,200 tokens | 3,807 lines / ~44,400 tokens |
| --- | --- | --- |
| whole file | missed, 2 of 2 | missed, 2 of 2 |
| `--diff`, changed lines marked | **found, 3 of 3** | **found, 1 of 1** |

The defect was the same unguarded division each time, appended as the last
function in the file, cited correctly at line 877 and at line 3,807 with
`certain` confidence.

Three prompt variants were tried on the whole-file review before this was
found, each a general instruction Forge could have shipped - "review it from
its first line to its last", an explicit end-of-file marker after the code, and
both together. All three missed, returning the same empty findings list.

So the size is not what defeats the model, and neither is the file. **Telling
it to read to the end does nothing; marking the lines to look at works.** That
is the mechanism ADR-0008 chose for a different reason - so that a model could
judge a change with its surroundings visible - and it turns out to carry
attention as well.

This leaves the caveat saying something untrue. On a `--diff` run it tells a
user that a result which has been measured reliable at eleven times the
threshold "may only cover the start of the file". A caveat that fires where the
evidence says it should not is not caution; it is noise that teaches people to
ignore the caveat where it matters.

## Decision

The caveat is **printed for a whole-file review and suppressed for a change
review**.

Everything else in ADR-0011 stands unchanged: the 4,000-token threshold and why
it is the last size seen to work, judging on input tokens, stderr after the
result, and `--plain` not silencing it.

`--diff` was verified to 44,409 input tokens. `FORGE_MAX_FILE_BYTES` allows a
file of roughly 50,000 tokens, so the untested band above the measurement is
narrow, and a `--diff` run inside it is the case this decision is least sure
about. That is recorded rather than papered over with a caveat nobody would
read.

## Alternatives Considered

**Leave it firing on both.** Defensible for a day: the caveat is cheap and
erring loud is usually right. Rejected because it is now known to be false in
the `--diff` case, and the project's argument for the caveat was honesty. A
warning kept after it is known to be wrong is the same failure it was written
to prevent, pointed the other way.

**Reword it for `--diff` instead of suppressing it** - something like "changed
lines are reviewed reliably at this size". Rejected: it is a sentence saying
nothing went wrong, printed on every large change review, which is exactly the
kind of line users learn to skip.

**Suppress it only below the tested ceiling** and keep it for `--diff` runs
above 44,409 tokens. Rejected as a threshold invented to look careful. The band
between the measurement and the size limit is narrow, one measurement does not
locate a boundary inside it, and a number nobody measured is worse than a
recorded gap.

## Consequences

**Easier:**

- The caveat appears where it is true, which is the only condition under which
  it keeps working.
- `--diff` gains a reason to be preferred on a long file, and it is a measured
  one rather than a stylistic preference. The guide can now say so.

**Harder:**

- Two behaviours to keep straight instead of one, and a test for each.
- The whole-file review is still the mode that under-reports, and it is the
  default. Narrowing the caveat does not fix that, and it slightly reduces the
  pressure to - which is why the measurement below is written into
  `status.md` rather than left in this record alone.

**What it points at next:** marking works and instruction does not, so the fix
for the whole-file review is structural. Reviewing a long file as a series of
marked windows reuses the mechanism that already works, and the roadmap entry
for reviewing a long file in sections should be read in that light. It still
multiplies provider calls, and still needs its own decision.
