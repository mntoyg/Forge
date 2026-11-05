# ADR-0019 - Prepare result completeness metadata for JSON output

## Status

Accepted - owner approved on 2026-11-05

## Context

FR-4.4's owner-approved v1 JSON contract covers `forge debug` (including
`--diff`) and `forge inspect`. Human-readable output remains the default.
`forge review` and `forge explain` are excluded from v1. The detailed envelope,
fields, streams, and compatibility proposal is
[`json-output-contract.md`](../proposals/json-output-contract.md).

Before JSON serialization, the result models need typed completeness signals.
The debug parser can discard individual untrusted findings but currently
returns only accepted findings. The project evidence reader already reports
whether its bounded scan completed, but `ProjectOverview` currently drops that
state.

## Decision

Implement Phase 1 metadata only; do not add JSON serialization or CLI format
options in this phase.

- `ParsedFindings.incomplete` is `True` when one or more raw finding entries
  were discarded during parsing, and `False` when no entry was discarded. It
  carries no count. Propagate this value as `AnalysisResult.incomplete` with
  the same polarity. The field concerns parser omissions only; it does not
  claim the model found every issue.
- `ProjectOverview.scan_complete` is `True` when the bounded evidence scan
  completed within the reader's declared scope, and `False` when the reader
  reports an incomplete scan. Copy the value from `ProjectEvidence.complete`.
  Its polarity is intentionally positive and explicit.
- The future JSON layer may report `partial` when debug has a known size
  caveat or `AnalysisResult.incomplete` is true, or when inspect's
  `scan_complete` is false. It may report `complete` when these typed signals
  establish that no known processing omission occurred within the declared
  scope. It must not imply AI completeness or correctness. Use `unknown` if
  the required signal is unavailable.
- Preserve ADR-0006 exit codes, current text output, and all provider behavior.
  Parsing remains defensive under ADR-0007. The size caveat remains governed
  by ADR-0012, including its whole-file-only behavior.
- No JSON support is added to `review` or `explain` in v1.

## Alternatives considered

- **Infer completeness later from rendered text.** Rejected because wording is
  not stable typed data and cannot distinguish a real omission from a normal
  scope note.
- **Add rejected-entry counts.** Rejected because consumers need only know
  whether the result is incomplete, and counts are not part of the approved
  contract.
- **Add JSON serialization in the same change.** Rejected for this phase so
  result metadata can be reviewed independently before introducing the public
  CLI output surface.

## Consequences

- Future serialization can distinguish known parser/scan omissions without
  parsing prose or exposing provider-controlled data.
- Result models gain additive fields; existing human rendering and command
  exit behavior remain unchanged.
- Completeness describes known processing coverage only. `complete` does not
  assert that an AI analysis is exhaustive or correct.

## Phase 1 acceptance

- Deterministic tests cover retained and discarded debug entries and complete
  and incomplete inspect scans.
- No finding rejection count is exposed.
- No JSON serializer, format option, dependency, provider call, or exit-code
  change is introduced.
