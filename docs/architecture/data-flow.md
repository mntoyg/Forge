# Data Flow

How requests travel through the layers. The version flag, `forge debug`, and
`forge inspect` are implemented; the diagrams below show the command paths.

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

The remaining diagrams show the command paths through the layers.

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

## Implemented flow: `forge inspect [directory]`

```text
  User
    | forge inspect [directory]
    v
  CLI (cli/inspect.py)
    | InspectProject(directory)
    v
  Application (application/inspect.py)
    | ProjectEvidenceReader port
    v
  Infrastructure (infrastructure/project.py)
    | bounded snapshot: known metadata, guidance paths, shallow tree
    v
  Application derives evidence-backed facts
    v
  Presentation renders overview and any omissions
    v
  stdout / stderr, exit code
```

This path is local and deterministic. It does not call the provider, execute
commands, or modify the selected project. Discovery resolves the selected root,
does not follow symlinks, filters ignored and sensitive paths, and stops at
the declared file and byte limits. The output identifies the files that
support each reported fact and states when evidence is missing or the scan is
incomplete.

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
