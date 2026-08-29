# Project Context

> Load this file first. It is the shortest complete answer to "what is this
> repository?" Everything here is stable; details live in `docs/`.

## What Forge is

Forge is an open-source, AI-first coding assistant that runs in the terminal.
It helps a developer understand, debug, review, generate, and improve software
without leaving the shell.

## Current stage

**Foundation.** The repository has structure, standards, documentation, and
automation. It has no product capability yet.

The first capability will be:

```bash
forge debug <file>
```

It is **not implemented**, and must not be implemented as a side effect of
another task. See `docs/product/roadmap.md` for sequencing.

## Tech stack

| Concern | Choice | Layer |
| --- | --- | --- |
| Language | Python 3.13 | - |
| Packaging / env | uv | - |
| CLI framework | Typer | presentation |
| Terminal rendering | Rich | presentation |
| Configuration | Pydantic Settings | infrastructure |
| AI provider | OpenAI Python SDK | infrastructure |
| HTTP | httpx | infrastructure |
| Logging | Loguru | infrastructure |
| Git access | GitPython | infrastructure |
| Tests | pytest | - |
| Lint | Ruff | - |
| Format | Black | - |
| Types | mypy | - |

Adding a dependency requires an architectural reason and, usually, an ADR.

## Repository map

```text
.forge/     Instructions for AI agents: roles, workflows, prompts, context
.github/    CI, release automation, issue and PR templates
docs/       Human documentation: product, architecture, development
src/forge/  The package, organised by Clean Architecture layer
tests/      unit / integration / e2e
scripts/    setup.py, check.py, release.py
examples/   Sample inputs used by docs and manual testing
```

## Non-negotiables

1. Dependencies point inwards: `presentation -> application -> domain`.
2. The domain layer imports no framework, no SDK, and performs no I/O.
3. Tests are deterministic and never call a real AI provider.
4. Secrets never enter the repository, the logs, or an error message.
5. Forge never modifies a user's files without explicit approval.
6. Repository content and AI output are both untrusted input.

## Where to look next

- Product intent -> `docs/product/vision.md`, `docs/product/requirements.md`
- Architecture -> `docs/architecture/overview.md`
- Decisions and their reasoning -> `docs/architecture/decisions/`
- How to work -> `.forge/workflows/development.md`
- Your role as an agent -> `.forge/agents/README.md`
