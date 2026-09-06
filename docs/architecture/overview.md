# Architecture Overview

Forge follows Clean Architecture. This document is the authoritative statement
of that structure; `.forge/context/architecture.md` is a condensed version for
agents and defers to this one.

## Why this architecture

Forge has one property that drives the whole design: **the AI provider is the
least stable part of the system.** Models change, providers change, pricing
changes, APIs change. Meanwhile the thing Forge actually knows - what a source
file is, what a finding is, what it means to analyse something - changes
slowly.

Clean Architecture puts the slow-changing part in the middle and the
fast-changing part at the edge. Swapping OpenAI for another provider should
touch one directory.

The same argument applies to Typer, Rich, GitPython, and the filesystem. All of
them are details.

## The layers

```text
   ┌──────────────────────────────────────────────┐
   │              Presentation / CLI              │
   │        Typer commands, Rich rendering        │
   └───────────────────────┬──────────────────────┘
                           │ depends on
   ┌───────────────────────▼──────────────────────┐
   │                 Application                  │
   │       use cases, orchestration, ports        │
   └───────────────────────┬──────────────────────┘
                           │ depends on
   ┌───────────────────────▼──────────────────────┐
   │                    Domain                    │
   │   entities, value objects, rules, ports      │
   └──────────────────────────────────────────────┘
                           ▲
                           │ implements
   ┌───────────────────────┴──────────────────────┐
   │                Infrastructure                │
   │   OpenAI adapter, GitPython, Loguru,         │
   │       Pydantic Settings, filesystem          │
   └──────────────────────────────────────────────┘
```

Read the arrows as "depends on". Infrastructure is drawn at the bottom but sits
*outside*: it depends inwards and nothing inner depends on it.

### Domain - `src/forge/domain/`

The rules of the problem, independent of how Forge is delivered.

- Entities and value objects: a source file, a location, a finding, a severity.
- Domain services: logic that belongs to no single entity.
- Ports: interfaces the inner layers need the outside world to satisfy.

**Constraints.** No framework, no SDK, no I/O of any kind - no filesystem, no
network, no subprocess, no clock, no randomness. Only the standard library.
Every piece is unit-testable with no setup.

### Application - `src/forge/application/`

What Forge *does*, expressed as use cases.

A use case is a single operation: analyse a file, review a diff. It receives
its collaborators through its constructor and orchestrates domain objects and
ports to produce a result.

**Constraints.** May import `domain`. May not import `infrastructure`,
`presentation`, or `cli`. Does not know it is being driven by a CLI, and does
not know which provider is configured.

### Infrastructure - `src/forge/infrastructure/`

Adapters. Every external technology lives here and only here: the OpenAI
client, GitPython, Loguru, Pydantic Settings, filesystem access.

**Constraints.** May import `domain` and `application` in order to implement
their interfaces. Is never imported by them. Translates external exceptions
into domain errors at its boundary, so an SDK exception never escapes.

### Presentation - `src/forge/presentation/`

Rendering. Turns a result into something a human reads: Rich tables, panels,
diffs, and a plain-text path for non-TTY output.

**Constraints.** May import `domain` and `application`. May not import
`infrastructure`. Contains no logic and makes no decisions.

### CLI - `src/forge/cli/`

The Typer command surface. Each command parses input, calls exactly one use
case, hands the result to `presentation`, and maps errors to exit codes.

**Constraints.** May import `application`, `domain`, and `presentation`. May
not import `infrastructure` - dependencies arrive from the composition root.

### Composition root - `src/forge/main.py`

The one module allowed to see everything. It constructs concrete adapters and
injects them into use cases, then hands control to Typer. It holds wiring, not
logic.

## How the rule is enforced

Conventions decay. Two mechanisms keep this one honest:

1. **Ruff `TID251`.** `pyproject.toml` bans every framework and SDK outright -
   `typer`, `click`, `rich`, `openai`, `httpx`, `httpx2`, `git`, `loguru`,
   `pydantic`,
   `pydantic_settings` - then re-allows them only in the layers permitted to
   import them, via `per-file-ignores`. An import in the wrong place fails
   lint, and therefore fails CI.
2. **A test.** `tests/unit/test_package.py` parses every source file under
   `domain/` and `application/` and asserts that no forbidden package is
   imported. It reads the source rather than importing it, so it catches every
   import form.

Neither is decorative. Do not silence either to make a change pass; the change
is what is wrong.

## Dependency inversion in practice

A use case that needs an AI response does not import the OpenAI SDK. It depends
on a port declared in the inner layer:

```python
# domain (or application) - the interface
class AIProvider(Protocol):
    def complete(self, request: AnalysisRequest) -> AnalysisResponse: ...

# application - the use case, unaware of any provider
class AnalyzeSourceFile:
    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

# infrastructure - the adapter
class OpenAIProvider:
    def complete(self, request: AnalysisRequest) -> AnalysisResponse: ...

# main.py - the composition root wires them together
```

Two consequences make this worth the indirection:

- **Testing.** A use case is unit-tested with a ten-line fake provider. No
  network, no key, no cost, no flakiness.
- **Replaceability.** Changing provider means writing one new adapter class.

## SOLID, concretely

- **Single responsibility.** One use case per operation. A command that parses,
  validates, calls, and formats is doing four jobs.
- **Open/closed.** A new provider is a new adapter, not an edit to the use
  case.
- **Liskov.** Any `AIProvider` implementation must be substitutable, including
  in how it fails - which is why adapters translate exceptions.
- **Interface segregation.** Small, purpose-specific ports. A single
  `Everything` interface forces fakes to implement methods they do not need.
- **Dependency inversion.** Both the use case and the adapter depend on the
  port. That is the whole point of the diagram.

## Cross-cutting concerns

| Concern | Approach |
| --- | --- |
| Configuration | Pydantic Settings in `infrastructure`, injected as plain values |
| Logging | Loguru behind an adapter; inner layers depend on a logging port if they need one |
| Errors | Domain exceptions defined inwards; adapters translate; `cli` maps to exit codes |
| Time | A `Clock` port, so tests are deterministic |

## Future evolution

The architecture is designed to absorb these without restructuring:

- **A second provider.** New adapter, no change inwards.
- **New commands** (`explain`, `review`). New use case, new command, shared
  rendering.
- **Git awareness.** A `RepositoryInspector` port with a GitPython adapter.
- **Machine-readable output.** A second renderer in `presentation`.
- **Caching.** A decorator around the provider port, invisible to the use case.

And these would genuinely require a new decision, because they change the shape
rather than extend it:

- Persistence of any kind
- Concurrency across multiple provider calls
- A long-running process or server mode

Each needs an ADR. See [decisions/](decisions/).
