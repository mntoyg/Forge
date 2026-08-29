# Development Workflow

The standard path from a requirement to merged code. Every non-trivial change
follows it.

```text
Requirement
    |
    v
Clarification
    |
    v
Architecture
    |
    v
Architecture Review
    |
    v
Implementation Plan
    |
    v
Implementation
    |
    v
Tests
    |
    v
Lint
    |
    v
Type Check
    |
    v
Code Review
    |
    v
Security Review
    |
    v
Merge
```

## The steps

| # | Step | Owner | Output |
| --- | --- | --- | --- |
| 1 | Requirement | Human / issue | A stated problem, not a solution |
| 2 | Clarification | Any agent | Open questions answered; scope agreed |
| 3 | Architecture | ChatGPT | Design: layers, ports, data flow |
| 4 | Architecture Review | Gemini | Verdict + failure modes + scalability |
| 5 | Implementation Plan | ChatGPT or Claude Code | Files, order, tests |
| 6 | Implementation | Claude Code / Cursor / Aider | The diff |
| 7 | Tests | Same agent as step 6 | Tests at the right level |
| 8 | Lint | Automated | `uv run ruff check .` clean |
| 9 | Type Check | Automated | `uv run mypy` clean |
| 10 | Code Review | Human + agent | Approved diff |
| 11 | Security Review | Human + agent | No secret, no unsafe path, no exec |
| 12 | Merge | Human | Squash-merged into `main` |

Steps 8 and 9 run together locally through `uv run python scripts/check.py`,
and again in CI. They are gates, not suggestions: a red gate is not merged.

## Choosing the right weight

Not every change needs twelve steps.

### Trivial change - simplified workflow

A typo, a comment, a docstring, a version bump, a test-only addition that
covers existing behaviour.

```text
Change -> Tests/Checks -> Code Review -> Merge
```

Steps 3, 4, 5, and 11 are skipped. Say in the PR that you took the simplified
path.

### Standard change - full workflow

A new command, a new use case, a bug fix with a behavioural change, anything
touching more than one layer. All twelve steps.

### Architectural change - full workflow plus an ADR

Anything in the "when a new ADR is required" list in
`.forge/context/decisions.md`. The ADR is written and accepted **before**
implementation, not alongside it. See
[architecture-change.md](architecture-change.md).

## Clarification: what to ask

Ambiguity that changes the result is worth a question. Ambiguity that does not
is worth a stated assumption and a note in the PR.

Good questions at this stage:

- What is the user actually trying to accomplish?
- What is explicitly out of scope?
- What does the output look like when it succeeds, and when it fails?
- Which existing behaviour must not change?

## Definition of ready (before step 6)

- The problem is written down.
- The design names the layers and ports involved.
- The review verdict is recorded.
- The test plan says which level covers what.
- No unresolved ADR conflict remains.

## Definition of done (before step 12)

- `uv run python scripts/check.py` passes.
- Tests cover the new behaviour, including its failure path.
- Documentation touched by the change is updated.
- `CHANGELOG.md` has an entry under `Unreleased`, if user-visible.
- The commit history is clean and conventional.
- A human has read the whole diff.
