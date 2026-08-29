# ADR-0004 - Typer for the CLI

## Status

Accepted - 2026-01-01

## Context

Forge is a command-line tool. The CLI is its entire user interface, so the
framework choice affects every user interaction: argument parsing, help text,
validation errors, exit codes, and shell completion.

Requirements for the choice:

- Subcommands, since `debug` is the first of several planned verbs.
- Type-annotated argument definitions, so the CLI layer is checked by the same
  mypy run as everything else.
- Good help output without hand-writing it.
- A testing story that does not require spawning a subprocess.
- Small dependency footprint.

A constraint from ADR-0002 shapes this: whatever we choose, it must stay inside
`cli/` and `main.py`. Nothing in `application/` or `domain/` may know which CLI
framework is in use, so this decision must be cheap to reverse.

## Decision

We will use **Typer** for the command surface.

- Commands are defined with type annotations; Typer derives parsing and help
  from them.
- Typer imports are confined to `cli/` and `main.py`, enforced by Ruff
  `TID251`.
- Commands stay thin: parse, call one use case, render, map the error to an
  exit code.
- Tests use Typer's `CliRunner`, so the CLI is tested in-process with no
  subprocess and no installed binary.

## Alternatives Considered

**argparse (standard library).** No dependency at all, and available
everywhere. Rejected because subcommand definitions are verbose, the help
output needs hand-tuning, and nothing connects the parser to type annotations -
so the CLI layer would be the one place mypy could not help us.

**Click.** Mature, widely used, and the library Typer is built on. A perfectly
defensible choice. Rejected only because Typer sits on top of it and adds the
type-annotation-driven definitions we want; choosing Click would mean writing
decorators by hand for the same result. We inherit Click's maturity either way.

**Fire.** Generates a CLI from arbitrary Python objects with almost no code.
Rejected because the generated interface follows the code's shape rather than a
designed command contract, and the help output is not good enough for a tool
whose interface is its product.

**A hand-rolled parser.** Zero dependencies and total control. Rejected as
obvious wheel-reinvention with no benefit; the effort belongs in the product.

## Consequences

**Easier:**

- Command definitions are short and readable, and mypy checks them.
- Help output is good by default.
- `CliRunner` makes end-to-end tests fast and hermetic.
- Shell completion is available if we later want it.

**Harder:**

- Two dependencies in practice, since Typer pulls in Click. Acceptable: both
  are small, stable, and widely deployed.
- Typer's magic (annotations driving behaviour) can obscure what is happening
  for a reader unfamiliar with it. Mitigated by keeping commands thin enough
  that there is little to obscure.
- A future Typer breaking change would touch every command file. Contained,
  because that is the only place it appears.

**Accepted:** Typer types must not appear in `application/` or `domain/`. If a
use case needs a value, the command extracts it and passes a plain type.
