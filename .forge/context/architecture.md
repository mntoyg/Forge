# Architecture Context (agent summary)

> This is the condensed version for agents working on a task. The full
> description is `docs/architecture/overview.md`; that document wins on any
> disagreement.

## Dependency direction

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

Infrastructure sits *outside* and points inwards. It implements interfaces the
inner layers declare. Nothing inner imports it.

## The rule that matters most

If you are editing `src/forge/domain/` or `src/forge/application/` and you find
yourself typing `import typer`, `import openai`, `import httpx2`, `import git`,
`from rich...`, or `from loguru...` - **stop**. You are about to invert the
dependency direction. Declare a port instead and implement it in
`infrastructure/`.

Ruff enforces this mechanically (`TID251` + `banned-api` in `pyproject.toml`),
and `tests/unit/test_package.py` checks it by parsing the source of both inner
layers. Do not silence either.

## Ports and adapters

A *port* is an abstract interface declared by the inner layer that needs it.
An *adapter* is the concrete implementation in `infrastructure/`.

Planned ports (none implemented yet - design them when the use case arrives):

| Port | Purpose | Adapter |
| --- | --- | --- |
| `AIProvider` | Send a prompt, get a structured response | OpenAI SDK |
| `SourceReader` | Read a source file safely | filesystem |
| `RepositoryInspector` | Query git history and diffs | GitPython |
| `Clock` | Current time | stdlib |

Do not create a port until a use case needs it. YAGNI applies.

## Wiring

`src/forge/main.py` is the composition root and the only module that may know
about every layer at once. It builds adapters and injects them into use cases.
Use cases never construct their own collaborators.

## Where things go

| You are adding... | It belongs in |
| --- | --- |
| A new `forge <command>` | `cli/` (thin), calling one use case |
| Business rule / invariant | `domain/` |
| A multi-step operation | `application/` as a use case |
| A call to any external system | `infrastructure/` behind a port |
| Formatting output for a human | `presentation/` |
| Wiring a concrete adapter | `main.py` |
