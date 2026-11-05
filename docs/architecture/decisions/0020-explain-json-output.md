# ADR-0020 - Add `forge explain` to machine-readable JSON output

## Status

Accepted - owner approved on 2026-11-05

## Context

FR-4.4 v1 is implemented for `forge debug` (including `--diff`) and
`forge inspect`, as recorded in ADR-0019. The owner approved adding the existing
single-file `forge explain <FILE>` command as an additive command under JSON
`schema_version: 1`. This extends the command scope without rewriting ADR-0019's
historical decision. `review` remains excluded because its consent flow needs
a separate contract.

The detailed field schema and diagnostic mapping are maintained in the
[explain JSON proposal](../proposals/explain-json-output-contract.md). The
current `ExplanationResult.incomplete` flag also covers limitations and
validation uncertainty, so JSON completeness needs a distinct typed signal.

## Decision

- Add `command: "explain"` to schema v1 as an additive command. Keep text as
  the default, preserve existing debug/inspect envelopes, and keep existing
  consumers compatible under the v1 additive-field/code rule.
- Reuse the existing `SourceReader`, `AIProvider`, and validated one-file
  result. Make at most one provider call; inspect no adjacent files, do not
  retry, and preserve the accepted FR-7 read-only boundary.
- Add `ExplanationResult.processing_incomplete: bool | None`. `True` means at
  least one claim or required field was omitted and has a stable omission
  diagnostic; `False` means no known parser omission and validation was
  available; `None` means validation availability prevents establishing that
  no omission occurred and no known omission already establishes `partial`.
  Any known omission takes precedence and yields
  `partial`; unavailable validation with no known omission yields `unknown`;
  otherwise completeness is `complete`. Preserve the legacy `incomplete`
  field and human rendering unchanged. The new validation-availability
  diagnostics are metadata-only and are not added to text output; existing
  limitations continue to explain those cases to text users.
- Add typed `SOURCE_VALIDATION_UNAVAILABLE` and
  `SYMBOL_VALIDATION_UNAVAILABLE` diagnostics when the source cannot be
  tokenized/validated or Python AST scope validation is unavailable. These
  diagnostics explain `unknown` when there is no known omitted claim. If a
  claim is discarded, its omission diagnostic makes the result `partial`.
- Keep the approved diagnostic classifications and stable completeness objects
  in the proposal: omission objects have `{code, section, count}`, warning
  objects have `{code, section}`, and informational diagnostics such as
  `SECTION_EMPTY` do not affect completeness. Counts represent diagnostic
  occurrences, never inferred rejected-claim totals. Context insufficiency,
  valid limitations, and a retained claim whose confidence is downgraded are
  warnings, not parser omissions.
- Serialize only the safe workspace-relative POSIX path. Resolve it against
  the invocation workspace before reading or calling the provider. Fail closed
  with `input_unusable` (exit 2) if a safe relative path cannot be derived;
  never emit an absolute path, workspace root, or parent path.
- In JSON mode, write one UTF-8 success envelope plus newline to stdout and
  suppress progress. A `ForgeError` writes one safe error envelope to stderr,
  leaves stdout empty, and preserves ADR-0006 exit codes. Help, syntax, and
  parameter errors raised before format selection retain text behavior.
  `--plain` remains accepted and redundant in JSON mode.
- Keep source excerpts, absolute paths, prompts, raw provider responses,
  exception text, secrets, credentials, base URLs, and environment data out of
  JSON. Preserve parsed claim and limitation text as untrusted provider output;
  validated citations locate claims but do not prove semantic correctness.
- Implement in reviewed stages. Stage A adds parser metadata and deterministic
  tests, with presentation filtering to keep text output unchanged. Stage B1
  adds the pure JSON serializer. Stage B2 adds CLI `--format` behavior with
  deterministic end-to-end tests. FR-4.4 explain support is complete only
  after all stages pass the repository gate.

## Alternatives considered

- **Change `ExplanationResult.incomplete` semantics.** Rejected because it
  would change existing text behavior. The new typed field separates JSON
  processing completeness.
- **Infer completeness from `incomplete`, limitations prose, or empty arrays.**
  Rejected because the flag combines uncertainty with omissions and prose is
  not stable typed metadata.
- **Put explain into a new schema major version.** Rejected because this is an
  additive command under the approved v1 compatibility rule; existing command
  envelopes remain unchanged.
- **Include `review` in this change.** Rejected because its plan-before-consent
  flow needs a distinct user interaction contract.

## Consequences

- `ExplanationResult` gains additive processing-completeness metadata and two
  validation-availability diagnostic kinds.
- Stage A changes no CLI flags, output, provider behavior, dependency, or exit
  code. Stage B will add the approved explain JSON surface in a separate
  reviewable change.
- ADR-0019 remains the historical decision for debug/inspect v1 scope.

## Stage A acceptance

- Parser tests cover known omission, warning-only, informational-only,
  validation-unavailable, and mixed validation/omission outcomes.
- A non-Python response with empty claim sections is `unknown`, while a
  discarded claim produces `partial` with its typed omission diagnostic.
- Python AST/tokenization-unavailable cases expose typed availability
  diagnostics and do not fabricate omission counts.
- Existing `incomplete` values, rendered text, provider call count, and
  one-file behavior remain unchanged.
- No serializer, CLI format option, live provider call, dependency, or exit
  behavior change is introduced in this stage.

## Stage B2 implementation status

Complete. `forge explain` now exposes `--format text|json`, validates the safe
relative path before reading or provider setup, and uses the approved success
and error serializers. Text remains the default, JSON suppresses progress, and
ADR-0006 exit codes are unchanged. Fake-provider CLI tests and the repository
quality gate verify the behavior. `review` remains excluded.
