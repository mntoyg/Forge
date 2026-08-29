# ADR-0001 - Python as the primary language

## Status

Accepted - 2026-01-01

## Context

Forge is a CLI tool whose core work is: read source files, talk to an AI
provider over HTTP, parse structured responses, and render results in a
terminal. It must be installable by developers on Linux, macOS, and Windows,
and it must be approachable enough that contributors can read the whole
codebase.

The forces:

- **AI SDK maturity.** Provider SDKs are best supported in Python, and Python
  is where new provider features arrive first.
- **Contributor reach.** An open-source developer tool lives or dies on how
  easy it is to submit a patch. Python has the largest overlap with the people
  likely to contribute.
- **Distribution friction.** A CLI written in an interpreted language needs a
  runtime present, which is a real cost.
- **Startup time.** A terminal tool that takes a second to start is
  irritating; a tool whose dominant cost is a network round trip is not.
- **Type safety.** The layered design depends on interfaces being checkable,
  not merely documented.

## Decision

We will use **Python 3.13** as the primary implementation language, with full
type annotations and mypy in strict mode.

3.13 specifically, so we can use modern syntax without compatibility shims and
avoid carrying support for versions that will be end-of-life during the
project's early life. `.python-version` pins it and `requires-python = ">=3.13"`
enforces it.

## Alternatives Considered

**Go.** A single static binary is the best possible distribution story for a
CLI, and startup is instant. Rejected because AI provider SDK support lags
Python, the contributor pool for this kind of tool is smaller, and Forge's
wall-clock time is dominated by a network call - so the startup advantage is
largely invisible to the user.

**Rust.** Same distribution advantage as Go, plus stronger guarantees.
Rejected for the same SDK-maturity reason, plus a materially higher barrier to
casual contribution. The safety Rust buys is aimed at a class of bug Forge does
not have.

**TypeScript / Node.** Good SDK support and a large contributor pool.
Rejected because Node's runtime dependency is no better than Python's for a
developer tool, and because Forge's primary users are developers who already
have Python available for other tooling.

**Python, but an older minimum (3.11 or 3.12).** Broader immediate
availability. Rejected because the compatibility cost is paid on every file for
the life of the project, and uv makes installing a specific Python version
trivial.

## Consequences

**Easier:**

- Direct use of the best-supported AI provider SDKs.
- A low barrier for contributors.
- Modern typing, so layer interfaces are checked and not just described.
- Rich and Typer, which are among the best terminal libraries in any ecosystem.

**Harder:**

- Distribution requires a Python runtime. We accept this for now; packaging as
  a standalone binary is a Phase 5 question, not a language question.
- Startup is slower than a compiled binary. Acceptable given that a provider
  round trip dominates.
- Runtime type errors remain possible where third-party code is untyped. Strict
  mypy plus adapter boundaries limit the blast radius.

**Accepted:** Python is a decision for the whole project. Introducing a second
implementation language requires a new ADR superseding this one.
