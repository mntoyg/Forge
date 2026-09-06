# ADR-0009 - History annotates the answer; the model never sees it

## Status

Accepted - 2026-09-01

## Context

Phase 3 ends with one item: give a finding the history of the line it points
at. The motivation is that git already knows something the model cannot. A line
last touched three times this month is a different risk from the same line
untouched for two years, and a reader deciding which of six findings to act on
first is exactly the person that difference is useful to.

Two facts are cheaply available and genuinely load-bearing:

- **who last changed the cited line, and when** - `git blame`
- **how much the file as a whole has been moving** - `git log` over a window

Something has to decide where those facts go. That choice is not obvious, and
it decides both what the run costs and how much of the output a reader can
trust.

Four forces:

- **A fact and a claim must not arrive through the same channel.** ADR-0007
  treats model output as untrusted input: a finding is a claim by something
  that can be wrong. Git history is not a claim. If both reach the reader
  inside the same JSON object, nothing in the output distinguishes them, and
  the more trustworthy half is dragged down to the reliability of the other.
- **A model asked to weigh evidence will assert things about it.** Told that a
  line changed four times, a model will explain what those four changes were.
  It cannot know.
- **Tokens are the user's money.** ADR-0008 already conceded that `--diff`
  buys focus rather than price. Adding a per-line history block to every prompt
  spends more, on every run, for a signal the reader can weigh unaided.
- **The annotation must not be able to break the run.** History exists only
  inside a repository, and only for a file that has been committed. A run that
  works today must not start failing because the file was copied somewhere
  else.

No trigger in `.forge/context/decisions.md` strictly applies: GitPython is
already a declared dependency, no layer boundary moves, and the CLI contract
is unchanged. This record exists for the same reason ADR-0008 does - the
decision is non-obvious and the alternatives are real.

## Decision

We will **look history up after the analysis, attach it to the result, and
render it beside the finding**. It is never added to the prompt.

```text
[HIGH] (line 16) Divides by len(values) without guarding an empty list
    average([]) raises ZeroDivisionError.
    confidence: certain
    history: last changed 2026-07-04 by A U Thor (a1b2c3d)
```

Supporting decisions:

- The `RepositoryInspector` port grows one method, `history(path, lines)`. It
  is asked only about the lines findings actually cite, so the cost of the
  annotation stays proportional to the answer being annotated - and a clean
  file asks nothing at all.
- **Blame runs against the working tree, not `HEAD`.** Line numbers then mean
  what they mean to a finding. Blaming `HEAD` would misattribute every line
  below an uncommitted insertion, on exactly the file this is most often run
  on: one that has just been edited.
- **An uncommitted line gets no record**, and the output says `not committed
  yet`. Git can name no commit for it, and naming the previous author would
  attribute the developer's own unsaved work to somebody else.
- **File churn is a count over a 90-day window, printed with its window.** A
  count with no period attached is a number nobody can read.
- **A repository that cannot answer is not a failed run.** Every
  `RepositoryError` raised by the lookup becomes "no history": the findings
  were produced and paid for before it was asked.
- **Dates are absolute.** "3 days ago" needs a clock, which would make the
  output depend on when it was rendered; a date is the same fact and is still
  true in a log read next month.
- **Author names are cleaned at the adapter boundary.** A name is whatever
  somebody put in their git config - untrusted input, and unlike a source file
  it is printed rather than analysed.

## Alternatives Considered

**Put the history in the prompt and let the model weigh it.** The version that
could improve the judgement rather than only the presentation: a model told a
line is churning might rank it higher. Rejected for now on three counts. It
spends input tokens on every run. It invites the model to assert history it
cannot verify, and once a claim about history is inside the findings JSON it is
indistinguishable - to the parser and to the reader - from a claim about the
code. And the benefit is a hypothesis: nothing measured so far says a model
ranks better with churn data than a developer does with the same line in front
of them. Revisit with evidence, not with enthusiasm.

**Do both.** Annotate the output *and* prompt with the history. Rejected as the
union of the costs before either has earned its place. The annotation is the
cheap half and the half that cannot mislead; shipping it alone is also what
produces the evidence the prompt version would need.

**Per-line churn, via `git log -L`.** Closest to the sentence that motivated
the work - "this line changed three times last week". Rejected on cost: it is
one git process per cited line, and the walk it performs is unbounded on a
repository with deep history, which turns a fast annotation into an
unpredictable one. The per-file count answers most of the same question at a
fixed cost of one call. Worth revisiting if per-line churn turns out to be what
people actually want.

**Show history only with `--diff`.** Tidy, and it keeps the default output
exactly as it is. Rejected because the annotation is context for a *finding*,
and a finding is a finding whether or not the run was scoped to a change. The
reader reviewing a whole file has the same question about the same line.

**Put it behind a `--history` flag.** The conservative option. Rejected
because the data costs no tokens and comes from a local process in
milliseconds; a flag would hide a free improvement behind something most users
never discover. Revisit if the two git calls ever show up as latency on a large
repository.

## Consequences

**Easier:**

- A git fact and a model claim stay visibly separate, in the output and in the
  type system: `ChangeRecord` is a fact, `Finding` is a claim.
- The annotation costs no tokens, so it can be on by default without an
  argument about whether it earns its price.
- Rendering is deterministic. No clock is read, so no test asserts on one.
- Nothing depends on history being available, which is what lets it disappear
  silently outside a repository instead of degrading the command.

**Harder:**

- Two git calls per run that produced a located finding. Blame reads the whole
  file; on a very large file in a deep repository that is not free.
- The output is one line taller per located finding. That is the cost of the
  information, and it is dim in the Rich renderer for that reason.
- `git blame` output is now a format Forge parses, which is a second thing that
  can change under us. `--line-porcelain` is used rather than `--porcelain`
  because the compressed form omits repeated headers, which would make the
  parser a cache - and a cache is a bug waiting for a large file.
- The captured sample runs in `README.md` and the getting-started guide predate
  this, and show no history line. They are real output and are left alone
  rather than edited to look like a run that never happened.

**Accepted:** history is decoration in the strict sense. Nothing depends on it,
nothing fails without it, and no answer changes because of it. That property is
precisely what makes it safe to have on by default.
