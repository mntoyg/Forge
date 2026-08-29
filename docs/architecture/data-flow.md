# Data Flow

How a request travels through the layers. The flow below describes the planned
`forge debug` command; **it is a design, not a description of existing code.**
Today only the version flag and the help output exist.

## Current flow

```text
$ forge --version

  shell
    |
    v
  main.py            Typer parses arguments
    |
    v
  _version_callback  reads forge.__version__
    |
    v
  stdout             "forge 0.0.1"   exit 0
```

That is the whole of it. Everything below is Phase 1 and Phase 2 design.

## Planned flow: `forge debug <file>`

```text
  User
    |  forge debug src/app.py
    v
┌───────────────────────────────────────────────────────────┐
│ CLI  (cli/)                                               │
│  - Typer parses the path argument                         │
│  - receives the use case, already wired, from main.py     │
└───────────────────────┬───────────────────────────────────┘
                        │ AnalyzeSourceFile(path)
                        v
┌───────────────────────────────────────────────────────────┐
│ Application  (application/)                               │
│  - asks SourceReader for the file                         │
│  - builds a domain request                                │
│  - asks AIProvider for an analysis                        │
│  - turns the response into domain Findings                │
└──────┬──────────────────────────────────┬─────────────────┘
       │ SourceReader port                │ AIProvider port
       v                                  v
┌──────────────────────┐          ┌───────────────────────────┐
│ Infrastructure       │          │ Infrastructure            │
│  filesystem adapter  │          │  OpenAI adapter           │
│  - resolve path      │          │  - build the request      │
│  - workspace check   │          │  - apply timeout          │
│  - size check        │          │  - call the SDK           │
│  - decode            │          │  - translate exceptions   │
└──────────┬───────────┘          └───────────┬───────────────┘
           │ SourceFile                       │ raw response
           v                                  v
┌───────────────────────────────────────────────────────────┐
│ Domain  (domain/)                                         │
│  SourceFile, Location, Finding, AnalysisResult            │
│  validation and invariants - no I/O                       │
└───────────────────────┬───────────────────────────────────┘
                        │ AnalysisResult
                        v
┌───────────────────────────────────────────────────────────┐
│ Presentation  (presentation/)                             │
│  Rich renderer (TTY)  |  plain renderer (pipe, CI)        │
└───────────────────────┬───────────────────────────────────┘
                        v
                    stdout / stderr, exit code
```

## Reading the diagram

Two things are worth noticing, because they are the architecture in action:

1. **The application layer names ports, not technologies.** It says
   `SourceReader` and `AIProvider`. It never says "filesystem" or "OpenAI".
   Replacing either is a change at the edge.
2. **Nothing flows back inward except domain types.** The OpenAI adapter
   returns a domain object, not an SDK response object. That translation is the
   boundary, and it is the reason an SDK change cannot ripple inwards.

## Error flow

Errors travel the same path in reverse, changing form at each boundary:

```text
  OSError / openai.APITimeoutError        (external)
            |
            v  translated at the adapter boundary
  SourceUnreadable / ProviderTimeout      (domain error)
            |
            v  propagated unchanged
  Application - may add context, never swallows
            |
            v  mapped in cli/
  Message on stderr + a specific exit code
```

An SDK exception type must never reach `application` or `cli`. If it does, an
adapter is missing its translation, and that is a review finding.

## What the user sees for each failure

| Failure | Where detected | Exit code | Message shape |
| --- | --- | --- | --- |
| File does not exist | source adapter | 2 | The path, and that it was not found |
| Path outside workspace | source adapter | 2 | Refusal, and why |
| File too large | source adapter | 2 | The size, and the limit |
| Binary or undecodable | source adapter | 2 | That it is not text |
| No API key configured | config | 3 | Which variable to set |
| Provider timeout | provider adapter | 4 | That it timed out, and the timeout |
| Rate limited | provider adapter | 4 | That it was rate limited, and to retry |
| Malformed model output | application | 1 | That the response could not be parsed |

Every one of these is a test case. Failure paths are behaviour, not
afterthoughts.

## Testing each seam

| Seam | How it is tested |
| --- | --- |
| Domain rules | Unit tests, no setup |
| Use case | Unit tests with a fake `SourceReader` and a fake `AIProvider` |
| Source adapter | Integration tests against `tmp_path` |
| Provider adapter | Integration tests against a stubbed transport - never a live API |
| Renderers | Unit tests asserting on the rendered string |
| Command | End-to-end tests through Typer's `CliRunner` |

The fakes are possible only because the ports exist. That is the practical
payoff of the whole structure.
