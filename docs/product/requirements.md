# Requirements

This is the top of the source-of-truth hierarchy. When an instruction anywhere
else conflicts with this document, this document wins.

Requirement IDs are stable. `MUST`, `SHOULD`, and `MAY` follow RFC 2119.

## Status legend

| Status | Meaning |
| --- | --- |
| Done | Implemented and covered by tests |
| Planned | Agreed, scheduled, not built |
| Deferred | Agreed in principle, explicitly not now |
| Excluded | Decided against; needs an ADR to revisit |

---

## FR-1 - Foundation

| ID | Requirement | Status |
| --- | --- | --- |
| FR-1.1 | The repository MUST expose an installable Python package named `forge`. | Done |
| FR-1.2 | The package MUST provide a `forge` console entry point. | Done |
| FR-1.3 | `forge --version` MUST print the package version and exit 0. | Done |
| FR-1.4 | Invoking `forge` with no arguments MUST show help rather than fail silently. | Done |
| FR-1.5 | The source tree MUST be organised into domain, application, infrastructure, presentation, and cli layers. | Done |
| FR-1.6 | The dependency direction MUST be enforced automatically, not by convention alone. | Done |

## FR-2 - Configuration

| ID | Requirement | Status |
| --- | --- | --- |
| FR-2.1 | Configuration MUST be read from environment variables, optionally via a local `.env`. | Done |
| FR-2.2 | All configuration keys MUST be prefixed `FORGE_`. | Done |
| FR-2.3 | An API key MUST NOT be readable from a command-line argument. | Done |
| FR-2.4 | A missing or invalid configuration MUST produce a clear, actionable message - never a traceback. | Done |
| FR-2.5 | Configuration values MUST NOT be printed or logged, even at `DEBUG`. | Done |
| FR-2.6 | `.env.example` MUST document every supported key with an empty value. | Done |

## FR-3 - `forge debug` (MVP capability)

| ID | Requirement | Status |
| --- | --- | --- |
| FR-3.1 | `forge debug <file>` MUST accept a path to a single source file. | Done |
| FR-3.2 | It MUST refuse a path that does not exist, is a directory, or is not readable, with a distinct exit code. | Done |
| FR-3.3 | It MUST refuse a path that resolves outside the current workspace. | Done |
| FR-3.4 | It MUST refuse a file above a configured size limit rather than truncating silently. | Done |
| FR-3.5 | It MUST send the file content to the configured AI provider through the provider port. | Done |
| FR-3.6 | It MUST render findings in a structured, readable form, each with a location where one is identifiable. | Done |
| FR-3.7 | It MUST NOT modify the analysed file or any other file. | Done |
| FR-3.8 | It MUST NOT execute the analysed file. | Done |
| FR-3.9 | It MUST exit non-zero when analysis could not be completed. | Done |
| FR-3.10 | It MUST report provider failures (timeout, rate limit, auth) as distinct, actionable messages. | Done |
| FR-3.11 | Where version control can answer, a finding SHOULD state when its line last changed and by whom. It MUST NOT fail the run when it cannot. | Done |

## FR-4 - Output

| ID | Requirement | Status |
| --- | --- | --- |
| FR-4.1 | Human-readable output MUST be the default. | Done |
| FR-4.2 | Output MUST degrade to plain text when stdout is not a TTY. | Done |
| FR-4.3 | Errors MUST go to stderr; results MUST go to stdout. | Done |
| FR-4.4 | A machine-readable output mode SHOULD exist for scripting. | Deferred |

## NFR-1 - Quality

| ID | Requirement | Status |
| --- | --- | --- |
| NFR-1.1 | All code MUST be fully type-annotated and pass mypy in strict mode. | Done |
| NFR-1.2 | All code MUST pass Ruff and Black checks. | Done |
| NFR-1.3 | The test suite MUST be deterministic. | Done |
| NFR-1.4 | Unit tests MUST NOT require an API key or network access. | Done |
| NFR-1.5 | CI MUST run format, lint, type, and test checks on every pull request. | Done |
| NFR-1.6 | Every user-facing behaviour MUST have a test. | Done |

## NFR-2 - Security

| ID | Requirement | Status |
| --- | --- | --- |
| NFR-2.1 | Secrets MUST NOT be committed to the repository. | Done |
| NFR-2.2 | Secrets MUST NOT appear in logs, errors, or terminal output. | Done |
| NFR-2.3 | Every file path MUST be validated against escape outside the workspace. | Done |
| NFR-2.4 | Forge MUST NOT execute arbitrary commands derived from file content or model output. | Done |
| NFR-2.5 | Forge MUST NOT modify user files without explicit approval. | Done |
| NFR-2.6 | Repository content and model output MUST be treated as untrusted input. | Done |

## NFR-3 - Usability

| ID | Requirement | Status |
| --- | --- | --- |
| NFR-3.1 | Every error message MUST state what went wrong and what to do next. | Done |
| NFR-3.2 | A long-running operation SHOULD show progress. | Planned |
| NFR-3.3 | The tool MUST run on Linux, macOS, and Windows. | Done |

## NFR-4 - Portability and cost

| ID | Requirement | Status |
| --- | --- | --- |
| NFR-4.1 | The AI provider MUST be replaceable without changing domain or application code. | Done |
| NFR-4.2 | The model MUST be configurable. | Done |
| NFR-4.3 | Forge SHOULD avoid sending more content than the task requires. | Done |

## Excluded

These are decided against. Reopening one requires an ADR.

| ID | Excluded | Reason |
| --- | --- | --- |
| EX-1 | Autonomous multi-step agents | Out of product scope; see [vision.md](vision.md) |
| EX-2 | Automatic file modification | Safety; the human applies changes |
| EX-3 | Executing user code | Safety |
| EX-4 | Databases and vector stores | Unnecessary complexity at this scope |
| EX-5 | LangChain / LangGraph or similar frameworks | The provider port is sufficient and keeps the dependency surface small |
| EX-6 | A hosted service | Forge is a local CLI using the user's own key |

## Traceability

Every pull request that changes behaviour references the requirement ID it
satisfies. A change that satisfies no requirement is either scope creep or a
missing requirement - resolve which before merging.
