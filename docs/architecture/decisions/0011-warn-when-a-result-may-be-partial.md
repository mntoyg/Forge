# ADR-0011 - Warn when a result may cover only the start of the file

## Status

Superseded by [ADR-0012](0012-the-caveat-is-for-whole-file-runs.md)

Accepted - 2026-09-06. The measurement below stands; what it did not test
was `--diff`, which turns out not to share the problem.

## Context

The first live run against a large file, made while gathering the last
evidence before `0.1.0`, produced a result the project cannot ship without
answering.

One unguarded division - the same defect `examples/buggy_division.py` gets
found for instantly, with `certain` confidence - was appended to the end of
real source files of four sizes and analysed against gpt-4o-mini:

| lines | input tokens | injected defect reported? |
| --- | --- | --- |
| 334 | 3,927 | yes, correct line, `certain` |
| 877 | 10,225 | no - and no findings at all |
| 1,922 | 23,359 | no - two unrelated findings instead |
| 3,807 | 44,295 | no - and no findings at all |

Size alone does not explain it. Moved to **line 6 of the same 877-line file**,
at the same 10,226 input tokens, it was found immediately. The model reads the
beginning of a long file and stops.

Three things make this urgent rather than interesting:

- **The failure is silent.** `no findings` is exactly what a clean file
  returns. A user gets the answer they hoped for and has no way to tell it
  apart from the model never having looked.
- **The limit we chose is twenty times past the evidence.**
  `FORGE_MAX_FILE_BYTES` defaults to 200,000 bytes. The tool was last seen
  working at roughly 4,000 input tokens.
- **The project already holds the principle.** `SourceTooLargeError` refuses to
  truncate, and says why: "analysing the first half of a file and reporting on
  it as if it were whole produces confident nonsense". The measurement says the
  model does precisely that, quietly, inside a limit Forge set itself.

## Decision

We will **analyse the file, and say plainly when the result may only cover its
start**.

```text
forge: core.py sent 44,221 tokens. Above roughly 4,000 the model has been seen
to stop reporting defects near the end of a file, so read this as an opinion on
the start of core.py rather than on all of it.
```

- **The threshold is 4,000 input tokens** - the last size that was *seen to
  work*, not the first that failed. Somewhere between 3,927 and 10,225 the tool
  stops being trustworthy, and nothing in the measurement says where. Choosing
  the failing end of that gap would mean promising something never observed.
- **It is judged on input tokens, not bytes**, because tokens are what the
  model actually had to read, and because the provider reports them - the count
  is measured rather than estimated.
- **It goes to stderr, after the result**, which is where the diagnostics
  already go: a piped stdout keeps carrying results and nothing else.
- **`--plain` does not silence it.** Plain output is about rendering; this is
  about whether the answer is complete.

## Alternatives Considered

**Lower `FORGE_MAX_FILE_BYTES` to match the evidence** - about 40KB - and
refuse anything larger. The most consistent with `SourceTooLargeError`, which
already prefers refusing to misleading. Rejected because the threshold is a
property of the *model*, not of Forge: a larger model plausibly reads much
further, and NFR-4.2 makes the model configurable precisely so users can bring
their own. A hard refusal would take a working tool away from a user whose
model is fine, on evidence gathered from one that is not.

**Split a long file across several calls and merge the findings.** The real
fix, and the only option that makes a long file genuinely reviewed. Rejected
*for 0.1.0*, not on merit: it multiplies provider calls per file, which is the
same cost argument that deferred the repository-wide sweep in ADR-0008, and it
raises questions this decision does not have to answer - where to cut, how much
overlap, how to reconcile duplicate findings across chunks. It belongs on the
roadmap with its own ADR.

**Document it and ship.** Cheapest, and it is what the status quo already
amounts to. Rejected because the documentation is not where the user is
standing when the tool says `no findings`. A caveat in a guide does not reach
somebody reading a terminal.

**Warn only when there are no findings.** Tempting - that is the case that
misleads most. Rejected because it is wrong: the 1,922-line run *did* return
two findings and still missed the injected one. A partial review is partial
whether or not it found something on the way.

## Consequences

**Easier:**

- The tool stops implying it read a file it did not. That is the vision's
  claim about honest output, applied to the one place it was failing.
- Nothing is taken away. A user with a model that reads further gets the same
  analysis they got before, plus a line they can ignore.
- It costs no tokens and no extra call; the number was already in the result.

**Harder:**

- The threshold is model-specific and will age. It is written down with the
  measurement that produced it so the next person can re-measure rather than
  guess what past-us meant.
- It will warn on files that were reviewed perfectly well. A false alarm is the
  price of choosing the last size that worked over the first that failed, and
  it is the right way round: an unnecessary caveat costs a moment, a missing
  one costs a defect.
- A warning is weaker than a fix, and the risk is that it becomes the permanent
  answer. It is recorded on the roadmap as the interim it is.

**Accepted:** for `0.1.0`, a user who is told the answer may be partial is in a
better position than one who is not, and that is worth shipping before the
chunking work that would make the warning unnecessary.
