# ADR-0002 - Clean Architecture

## Status

Accepted - 2026-01-01

## Context

Forge's parts change at very different rates.

The slow part is what Forge knows: what a source file is, what a finding is,
what it means to analyse code. The fast part is everything at the edge - the
AI provider, the model, the SDK, the CLI framework, the terminal renderer, the
git library. Providers deprecate endpoints; models are replaced; a CLI library
has a breaking release.

Two further forces:

- **Testability.** Any design that requires a real provider call to test a use
  case produces a slow, flaky, expensive suite - and therefore a suite people
  skip.
- **Multiple contributors, including AI agents.** A structure that relies on
  taste to stay coherent will not stay coherent. The rule has to be
  mechanically checkable.

## Decision

We will structure `src/forge/` as a **Clean Architecture** with four layers and
a composition root:

```text
presentation / cli  ->  application  ->  domain
infrastructure implements the ports declared by the inner layers
main.py is the composition root
```

Concretely:

- `domain/` - entities, value objects, rules, ports. No framework, no SDK, no
  I/O.
- `application/` - use cases. Depends only on `domain` and its ports.
- `infrastructure/` - adapters for every external technology.
- `presentation/` - rendering only.
- `cli/` - a thin Typer surface.
- `main.py` - the only module that sees all layers; it wires them.

And the rule is enforced, not merely stated:

1. Ruff `TID251` bans every framework and SDK globally, then re-allows each
   only in the layers permitted to use it.
2. `tests/unit/test_package.py` parses the source of `domain/` and
   `application/` and asserts no forbidden package is imported.

## Alternatives Considered

**A flat module layout.** Everything in `src/forge/`, organised by topic.
Simplest possible structure, and appropriate for a small script. Rejected
because the coupling it permits is exactly the coupling that makes provider
replacement expensive, and because it gives an AI agent no rule to follow.

**Layered but unenforced (convention only).** Same directories, no tooling.
Rejected on evidence: conventions erode under time pressure, and this project
expects contributions from several agents that will not infer an unstated rule.
The enforcement is the part that makes the layering real.

**Hexagonal architecture (ports and adapters).** Very close to what we chose,
and arguably the same idea with different vocabulary. Not rejected on merit -
the explicit four-layer naming simply maps more obviously onto directories,
which matters for agent instructions. We use its ports-and-adapters mechanics
throughout.

**Full vertical slice architecture.** Organise by feature rather than by layer.
Genuinely attractive for a larger application. Rejected because Forge has one
feature at the moment, and slicing by feature now would hide the
provider-replacement seam that motivated the whole design.

## Consequences

**Easier:**

- Replacing the AI provider touches one directory.
- Use cases are unit-tested against small fakes: fast, free, deterministic.
- Every contributor - human or agent - has one unambiguous question to answer
  for any new code: which layer does this belong to?
- Lint failures catch boundary violations before review does.

**Harder:**

- More indirection than the problem strictly requires today. A trivial feature
  touches four files instead of one.
- The port-and-adapter pair for a single-implementation dependency can feel
  like ceremony.
- Contributors unfamiliar with the pattern need to read the overview first.

**Accepted:** we take the indirection cost deliberately, because the seam it
buys sits exactly at the boundary we expect to churn. To limit the cost, YAGNI
applies inside the structure: **do not create a port until a use case needs
it.**

Changing the layer boundaries or the dependency direction requires a new ADR.
