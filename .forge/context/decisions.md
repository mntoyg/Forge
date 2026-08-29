# Decision Index (agent summary)

> Full records live in `docs/architecture/decisions/`. This index exists so an
> agent can see the accepted constraints without opening five files.

| ADR | Decision | Status | Binding constraint |
| --- | --- | --- | --- |
| [0001](../../docs/architecture/decisions/0001-python-as-primary-language.md) | Python 3.13 as the primary language | Accepted | No second implementation language without a new ADR. |
| [0002](../../docs/architecture/decisions/0002-clean-architecture.md) | Clean Architecture with four layers | Accepted | Dependencies point inwards; the domain stays pure. |
| [0003](../../docs/architecture/decisions/0003-ai-provider-abstraction.md) | AI access behind a provider port | Accepted | No layer except `infrastructure/` imports an AI SDK. |
| [0004](../../docs/architecture/decisions/0004-typer-for-cli.md) | Typer for the CLI surface | Accepted | Typer types stay in `cli/`; no `typer` import in inner layers. |
| [0005](../../docs/architecture/decisions/0005-uv-for-dependency-management.md) | uv for dependency and environment management | Accepted | `uv.lock` is committed; do not add pip/Poetry workflows. |

## How to use these

An accepted ADR is a constraint, not a suggestion. If a task appears to require
breaking one:

1. Stop implementing.
2. State which ADR is in the way and why the task conflicts with it.
3. Propose a superseding ADR with context, options, and consequences.
4. Wait for a human decision.

An ADR is never edited to change its decision. It is superseded by a new one,
and the old record is marked `Superseded by ADR-XXXX`.

## When a new ADR is required

- Adding or removing a runtime dependency.
- Changing the layer boundaries or the dependency direction.
- Choosing or replacing an external service or provider.
- Introducing persistence, caching, or concurrency.
- Changing the public CLI contract in a breaking way.

Not required for: renames, refactors within a layer, test additions,
documentation, formatting, or dependency version bumps.
