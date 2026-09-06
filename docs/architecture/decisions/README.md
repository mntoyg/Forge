# Architecture Decision Records

An ADR records a decision that shaped the system, along with the reasoning and
the alternatives that lost. The value is in the reasoning: six months from now,
the decision will be obvious from the code, but the trade-off will not be.

## Index

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-python-as-primary-language.md) | Python as the primary language | Accepted |
| [0002](0002-clean-architecture.md) | Clean Architecture | Accepted |
| [0003](0003-ai-provider-abstraction.md) | AI provider abstraction | Accepted |
| [0004](0004-typer-for-cli.md) | Typer for the CLI | Accepted |
| [0005](0005-uv-for-dependency-management.md) | uv for dependency management | Accepted |
| [0006](0006-exit-code-contract.md) | Exit code contract | Accepted |
| [0007](0007-structured-findings-by-prompt.md) | Structured findings by prompt | Accepted |
| [0008](0008-marked-file-for-change-analysis.md) | Marked file for change analysis | Accepted |
| [0009](0009-history-annotates-the-answer.md) | History annotates the answer | Accepted |
| [0010](0010-remove-httpx-dependency.md) | Remove httpx as a declared dependency | Accepted |
| [0011](0011-warn-when-a-result-may-be-partial.md) | Warn when a result may be partial | Superseded by 0012 |
| [0012](0012-the-caveat-is-for-whole-file-runs.md) | The caveat is for whole-file runs only | Accepted |

## When to write one

Write an ADR for a decision that is expensive to reverse or that constrains
future work:

- Adding or removing a runtime dependency
- Changing the layer boundaries or the dependency direction
- Choosing or replacing an external service or provider
- Introducing persistence, caching, or concurrency
- Breaking the public CLI contract

Do **not** write one for a rename, an internal refactor, a test, a
documentation change, or a version bump. An ADR for a trivial decision devalues
the ones that matter.

## Format

```markdown
# ADR-XXXX - <Title>

## Status
Proposed | Accepted | Rejected | Superseded by ADR-YYYY

## Context
The forces at play. What problem, what constraints, what was already true.
No solution here.

## Decision
What was decided, stated actively: "We will ...".

## Alternatives Considered
Each option genuinely on the table, and why it lost.

## Consequences
What becomes easier. What becomes harder. What we accept.
```

## Rules

- Numbers are sequential and never reused.
- An accepted ADR is never edited to change its decision. It is superseded by a
  new one, and its status becomes `Superseded by ADR-YYYY`.
- A rejected proposal is recorded too. It stops the same idea returning with no
  memory of why it lost.
- Only a human moves an ADR to `Accepted`.
- When an ADR is accepted, the documents derived from it are updated in the
  same pull request. See `.forge/workflows/architecture-change.md`.
