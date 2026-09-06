# Components

What exists today, and what each planned component will be responsible for.
Nothing marked *planned* is implemented, and none of it should be built ahead
of the requirement that needs it.

## Current components

| Component | Location | Responsibility | Status |
| --- | --- | --- | --- |
| Package root | `src/forge/__init__.py` | Version, layer documentation | Done |
| Composition root | `src/forge/main.py` | Build the Typer app, wire adapters | Done |
| Domain errors | `src/forge/domain/errors.py` | The error vocabulary every layer shares | Done |
| AI provider port | `src/forge/domain/ai.py` | The port and the value objects crossing it | Done |
| Configuration | `src/forge/infrastructure/config.py` | Typed `FORGE_*` settings, secrets protected | Done |
| Logging | `src/forge/infrastructure/logging.py` | Loguru, with redaction at the sink | Done |
| OpenAI adapter | `src/forge/infrastructure/openai_provider.py` | The provider port, implemented | Done |
| Fake provider | `tests/support/fakes.py` | Test doubles for both ports | Done |
| Source model | `src/forge/domain/source.py` | Findings, source files, the reader port | Done |
| Source reader | `src/forge/infrastructure/source.py` | Safe filesystem reads inside the workspace | Done |
| Prompt | `src/forge/application/prompt.py` | The analysis prompt (ADR-0007) | Done |
| Parser | `src/forge/application/parsing.py` | Defensive parsing of model output | Done |
| Analyse use case | `src/forge/application/analyze.py` | Read, ask, parse | Done |
| Renderers | `src/forge/presentation/findings.py` | Rich and plain output | Done |
| Debug command | `src/forge/cli/debug.py` | `forge debug <file>` | Done |
| Exit codes | `src/forge/cli/exit_codes.py` | The ADR-0006 contract, mapped once | Done |

Each layer package carries its dependency rules in its module docstring, so the
contract is visible where the code is written, not only in this document.

## Third-party dependencies and where each is allowed

| Dependency | Purpose | Allowed in |
| --- | --- | --- |
| Typer | Command parsing, help, exit codes | `cli/`, `main.py` |
| Rich | Terminal rendering | `presentation/`, `cli/` |
| Pydantic Settings | Typed configuration from the environment | `infrastructure/` |
| OpenAI SDK | Provider adapter | `infrastructure/` |
| httpx2 | The httpx the OpenAI SDK vendors | `infrastructure/` |
| Loguru | Structured logging | `infrastructure/` |
| GitPython | Repository inspection | `infrastructure/` |

Ruff enforces this table (`TID251`), and `tests/unit/test_package.py` mirrors
the same list for `domain/` and `application/`. If you need one of these
somewhere else, the answer is a port, not an exception.

### A note on httpx

The OpenAI SDK (v3) vendors its own httpx under the name `httpx2`, and this
trips people up the first time they see it. It is a different package from
`httpx`, and the two do not interchange: a client passed to the SDK must be an
`httpx2` client. `tests/integration/test_openai_provider.py` is where that
matters.

Forge itself declares no HTTP dependency. It held one until ADR-0010, on the
prediction that Phase 3 would bring HTTP work; Phase 3 brought git instead, and
a dependency nothing imports is one every installation pays for. The import ban
covers `httpx2` because that is the one actually present here - the day HTTP
returns, it returns with the code that calls it.

## Component detail

### Configuration - `infrastructure/config`

Reads `FORGE_*` variables through Pydantic Settings and exposes a validated,
immutable settings object. The API key is a `SecretStr`, so it survives no
`repr`, `str`, or `model_dump`. A missing or invalid value raises
`ConfigurationError` naming the variable at fault, and the rejected input is
deliberately excluded from the message - a user who types their key into the
wrong variable must not see it echoed back.

*Satisfies FR-2.1 to FR-2.6.*

### AI provider port and adapter

The port is a narrow interface: send a request, get a structured response. The
adapter wraps the OpenAI SDK, applies the configured timeout, and translates
every SDK exception into a domain error - `ProviderTimeoutError`,
`ProviderRateLimitError`, `ProviderAuthenticationError`,
`ProviderUnavailableError`, `ProviderResponseError` - so no SDK type escapes
the boundary.

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

`forge debug <file>` parses arguments, calls the analyse use case, hands the
result to a renderer, and maps domain errors to exit codes. It takes the use
case as a parameter rather than building one, so an end-to-end test drives the
real command surface against fakes.

Exit code allocation, binding per
[ADR-0006](decisions/0006-exit-code-contract.md). Mapping lives in
`cli/exit_codes.py` and nowhere else:

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Ran but could not produce a result, including an unparseable reply |
| 2 | Invalid input (missing file, unreadable, too large, outside workspace) |
| 3 | Configuration error |
| 4 | Provider error (timeout, rate limit, auth) |

*Satisfies FR-3.9, FR-4.3.*

### Repository inspector (Phase 3)

A port over GitPython for diffs, blame, and recent history, with defined
behaviour outside a git repository.

## Component interaction

See [data-flow.md](data-flow.md) for how these fit together at runtime.
