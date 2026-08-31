# ADR-0008 - Show the whole file with changes marked, not the diff

## Status

Accepted - 2026-08-31

## Context

Phase 3 adds the ability to analyse a *change* rather than a whole file:

```bash
forge debug app.py --diff
```

The motivation is what a developer actually does before committing. They do
not want an opinion on the whole file - they want an opinion on the twelve
lines they just wrote, and they do not want to pay for the rest.

Something has to decide what the model sees. That choice is not obvious, and
it determines both the quality of the answer and the cost of getting it.

Three forces:

- **A model cannot review what it cannot see.** A change to one line of a
  function is meaningless without the function. `- if x > 0:` / `+ if x >= 0:`
  is either a bug fix or a bug, and nothing in those two lines says which.
- **Line numbers must stay real.** FR-3.6 requires a location, and ADR-0007
  drops a location that falls outside the file rather than guessing. Any
  representation whose line numbers do not match the file on disk breaks that
  guarantee at the source.
- **Tokens are the user's money.** The whole point of `--diff` is to spend less
  than a full-file analysis, on the part that matters.

No ADR trigger in `.forge/context/decisions.md` strictly applies: GitPython is
already a declared dependency, no layer boundary moves, and adding a flag does
not break the CLI contract. This record exists because the decision is
non-obvious, has real alternatives, and introduces a port - not because a rule
demanded it.

## Decision

We will send the **whole file, numbered as usual, with changed lines marked**,
and tell the model to review the marked lines while using the rest as context.

```text
   14 |     def average(values: list[float]) -> float:
   15 >         if not values:
   16 >             return 0.0
   17 |         return sum(values) / len(values)
```

`>` marks a line the change touched; `|` marks context. The prompt states that
findings must concern the marked lines, and that problems in unmarked code are
out of scope for this run.

Supporting decisions:

- A **`RepositoryInspector` port** in the domain answers one question:
  which lines of this file were changed? The GitPython adapter lives in
  `infrastructure/`, and nothing inward learns that git exists.
- The comparison is the **working tree against `HEAD`** - staged and unstaged
  together, which is what "what I am about to commit" means to a developer
  mid-change.
- **Outside a git repository**, or for a file with no changes, the command
  says so plainly and exits `2`: the request cannot be satisfied as asked.
- The scope for now is **one named file**. Sweeping every changed file in a
  repository multiplies provider calls and cost in a way that deserves its own
  decision, not a silent consequence of this one.

## Alternatives Considered

**Send the raw unified diff.** The obvious answer, and the cheapest. Rejected
on two counts. The model sees only the hunks, so it reviews a change with no
sight of the function containing it - which is exactly the context needed to
tell a fix from a regression. And diff line numbers live in hunk headers
(`@@ -14,6 +14,8 @@`), so mapping a finding back to a real file line becomes
arithmetic the model has to perform correctly, on top of the analysis. It will
sometimes get it wrong, and a confidently wrong location is the failure
ADR-0007 exists to avoid.

**Send the diff with generous context** (`git diff -U30`). Cheaper than the
whole file, and it addresses the context problem for small files. Rejected
because it does not address the line-number problem, and because for the file
sizes Forge already accepts the saving is modest - a 200-line file with a
change in the middle is nearly all context anyway. It becomes worth revisiting
if the size limit rises substantially.

**Send only the changed lines.** Cheapest possible. Rejected outright: it
provides no context at all, and would produce confident nonsense about code
whose surroundings the model never saw.

**Send the whole file with no marking, and filter findings afterwards by line
number.** Simple to build, and reuses the existing prompt unchanged. Rejected
because it pays full price for a full-file analysis and then throws most of the
answer away - the user is billed for findings they never see. Filtering also
discards a finding whose location happens to be absent, which is precisely the
kind of whole-file observation `--diff` should not be reporting anyway.

## Consequences

**Easier:**

- The model reviews a change with the surrounding code in view, which is the
  only way to judge whether a change is correct.
- Line numbers are file line numbers throughout. Nothing has to be translated,
  so nothing can be translated wrongly.
- The existing pipeline is reused end to end - `SourceFile`, the parser, the
  renderers, the exit codes. `--diff` adds a set of integers and a prompt
  variant, not a second path through the system.
- The port keeps git out of the inner layers, so a future worktree, submodule,
  or non-git backend is an adapter change.

**Harder:**

- It costs full-file input tokens. `--diff` saves the user's *attention* and
  narrows the answer; it does not save much money. The output is smaller, and
  that is the honest extent of the saving.
- The marking is a second thing the prompt must be trusted to honour. A model
  may still report an unmarked line, so the prompt is explicit and the
  behaviour is tested against a recorded reply.
- A large file with a one-line change is the worst case for cost, and it is
  also the most common case. Revisit if the size limit ever rises.

**Accepted:** the saving from `--diff` is focus, not price. The help text and
the guide say so, because a user who expects a cheaper run and gets a
similarly-priced one has been misled by us rather than by the model.
