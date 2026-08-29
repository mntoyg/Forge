# Components

What exists today, and what each planned component will be responsible for.
Nothing marked *planned* is implemented, and none of it should be built ahead
of the requirement that needs it.

## Current components

| Component | Location | Responsibility | Status |
| --- | --- | --- | --- |
| Package root | `src/forge/__init__.py` | Version, layer documentation | Done |
| Composition root | `src/forge/main.py` | Build the Typer app, wire adapters | Done |
| Domain package | `src/forge/domain/` | Rules and ports | Skeleton |
| Application package | `src/forge/application/` | Use cases | Skeleton |
| Infrastructure package | `src/forge/infrastructure/` | Adapters | Skeleton |
| Presentation package | `src/forge/presentation/` | Rendering | Skeleton |
| CLI package | `src/forge/cli/` | Commands | Skeleton |

Each layer package carries its dependency rules in its module docstring, so the
contract is visible where the code is written, not only in this document.

## Third-party dependencies and where each is allowed

| Dependency | Purpose | Allowed in |
| --- | --- | --- |
| Typer | Command parsing, help, exit codes | `cli/`, `main.py` |
| Rich | Terminal rendering | `presentation/`, `cli/` |
| Pydantic Settings | Typed configuration from the environment | `infrastructure/` |
| OpenAI SDK | Provider adapter | `infrastructure/` |
| httpx | HTTP transport | `infrastructure/` |
| Loguru | Structured logging | `infrastructure/` |
| GitPython | Repository inspection | `infrastructure/` |

Ruff enforces this table (`TID251`), and `tests/unit/test_package.py` mirrors
the same list for `domain/` and `application/`. If you need one of these
somewhere else, the answer is a port, not an exception.

## Planned components

### Configuration - `infrastructure/config`

Reads `FORGE_*` variables through Pydantic Settings and exposes a validated,
immutable settings object. Never prints or logs a value. A missing key produces
an actionable message, not a traceback.

*Satisfies FR-2.x.*

### AI provider port and adapter

The port is a narrow interface: send a request, get a structured response. The
adapter wraps the OpenAI SDK, applies the configured timeout, and translates
every SDK exception into a domain error - `ProviderTimeout`, `RateLimited`,
`AuthenticationFailed`, `ProviderUnavailable` - so no SDK type escapes the
boundary.

A fake implementation lives in the test suite and returns canned responses.
That fake is what makes the use cases testable.

*Satisfies FR-3.5, FR-3.10, NFR-4.1.*

### Source reader - `infrastructure/source`

Reads a single file safely:

- Resolve the path and confirm it stays inside the workspace.
- Refuse a directory, a device, or an unreadable file.
- Refuse a file over the configured size limit rather than truncating.
- Decode explicitly, with a clear error on binary content.

*Satisfies FR-3.2, FR-3.3, FR-3.4, NFR-2.3.*

### Domain model

- `SourceFile` - path plus content, validated on construction.
- `Location` - file, line, optional column.
- `Finding` - a description, a severity, an optional location, and a
  confidence.
- `AnalysisResult` - a collection of findings plus what was analysed.

Value objects are frozen. An invalid instance must be impossible to construct.

### Analyse use case - `application/`

Takes a source path, uses the source reader and the provider port, and returns
an `AnalysisResult`. It knows nothing about Typer, Rich, or OpenAI. Its unit
tests use fakes for both ports.

*Satisfies FR-3.1, FR-3.6.*

### Renderers - `presentation/`

A Rich renderer for interactive terminals and a plain renderer for pipes and
CI. The choice is made by the CLI based on whether stdout is a TTY, so the
renderer itself stays a pure function of its input.

*Satisfies FR-4.1, FR-4.2.*

### Commands - `cli/`

`forge debug <file>` will parse arguments, call the analyse use case, hand the
result to a renderer, and map domain errors to exit codes.

Exit code allocation (proposed, to be fixed when the command is designed):

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Analysis completed but could not produce a result |
| 2 | Invalid input (missing file, unreadable, too large, outside workspace) |
| 3 | Configuration error |
| 4 | Provider error (timeout, rate limit, auth) |

*Satisfies FR-3.9, FR-4.3.*

### Repository inspector (Phase 3)

A port over GitPython for diffs, blame, and recent history, with defined
behaviour outside a git repository.

## Component interaction

See [data-flow.md](data-flow.md) for how these fit together at runtime.
