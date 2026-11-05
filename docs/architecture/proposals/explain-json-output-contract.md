# Proposed JSON output contract for `forge explain`

**Status: Proposed — awaiting owner approval.** This is a docs-only proposal.
It does not change FR-4.4 v1, which remains implemented for `debug` and
`inspect` only, or change CLI behavior. Do not implement until the owner accepts
the contract and the required decision record.

## Scope and compatibility

Add `forge explain <FILE> --format json` as an additive command under the
existing JSON envelope, `schema_version: 1`. Text remains the default, and the
existing debug and inspect envelopes stay unchanged. New consumers must opt in
by selecting `command: "explain"`; old consumers can ignore this new command.
`review` remains excluded: its plan-before-consent and result-after-consent
lifecycle needs a separate JSON interaction and consent protocol.

The proposal reuses the accepted one-file FR-7 contract, `SourceReader`,
`AIProvider`, evidence validation, and ADR-0006 exit codes. A selected file is
already sent to the configured provider by `forge explain`; JSON mode must not
read or send more files, add a call, retry, or otherwise expand that scope.

## Candidate success schema

```json
{
  "schema_version": 1,
  "command": "explain",
  "status": "success",
  "result": {
    "path": "src/app.py",
    "purpose": [{
      "text": "Coordinates a single-file explanation.",
      "confidence": "likely",
      "evidence": [{
        "kind": "call",
        "target": "self._provider.complete",
        "start_line": 18,
        "end_line": 18
      }]
    }],
    "main_flow": [],
    "important_symbols": [{
      "symbol": "ExplainSource",
      "text": "Reads one source snapshot and validates the provider response against it.",
      "confidence": "likely",
      "evidence": [{
        "kind": "return_value",
        "target": "parse_explanation",
        "start_line": 19,
        "end_line": 22
      }]
    }],
    "limitations": [],
    "context_insufficient": false,
    "incomplete": false,
    "model": "configured-model",
    "usage": {"input_tokens": 1200, "output_tokens": 180},
    "diagnostics": []
  },
  "completeness": {
    "status": "complete",
    "warnings": [],
    "omissions": []
  }
}
```

The schema is grounded in `ExplanationResult`:

- `path` is a workspace-relative POSIX path for the selected source. Never emit
  an absolute path, workspace root, or parent directory path.
- `purpose` and `main_flow` contain claim `text`, `confidence` (`certain`,
  `likely`, or `possible`), and validated `evidence`. `important_symbols`
  contains those same fields plus the exact declared `symbol` subject.
- Each evidence anchor contains `kind` (`call`, `access`, `return_type`,
  `return_value`, or `operation`), exact `target`, and inclusive, one-based
  `start_line` / `end_line`. These values come only from validated anchors in
  the submitted snapshot. JSON includes no excerpts or source lines.
- `limitations` contains the accepted limitation statements from the result;
  do not add source excerpts. `context_insufficient` and `incomplete` preserve
  the result's respective signals. `model` is the configured model identifier;
  `usage` contains the provider-reported input and output token counts.
- Each safe `diagnostics` entry contains only `section` (or null), `kind`, and
  positive `count`, corresponding to `ExplanationDiagnostic`. Never serialize
  diagnostic prose, raw validation input, or a provider-supplied reason.

Do not serialize `SourceFile.content`, rendered excerpts, prompts, raw provider
responses, exception strings, credentials, base URLs, environment values, or
other configuration. The structured claim and limitation fields are the
validated result already shown by text mode; do not add model response fields
or echo additional source data. Treat all claim and limitation text as
untrusted provider output.

## Completeness and context semantics

`ExplanationResult.incomplete` currently aggregates more than processing
omissions: the parser sets it for invalid or omitted claims and metadata, but
also for model-reported context insufficiency and non-Python evidence
validation limits. It must not be copied directly to
`completeness.status`. Likewise, `context_insufficient` is an uncertainty
signal; it does not prove that the bounded source read was incomplete.

Before implementation, add one additive typed signal to `ExplanationResult`:
`processing_incomplete: bool | None`. The parser sets it to `true` when claims,
evidence, or required response fields were omitted or could not be validated;
`false` when those processing steps completed without a known omission; and
`null` only when the signal is unavailable. This separates the serialization
decision without changing the existing `incomplete` field or its text-rendering
behavior. Owner review is required for this model addition.

Map it as follows:

- `processing_incomplete == true` -> `completeness.status: "partial"` and
  stable omission entries derived from the typed diagnostics.
- `processing_incomplete == false` -> `"complete"`; a true
  `context_insufficient` may add a `context_insufficient` warning, but does
  not change completeness. `complete` means bounded reading and the declared
  parsing/validation work completed without known omissions; it does not mean
  the explanation covers every behavior or is semantically correct.
- `processing_incomplete is null` -> `"unknown"`.

Never infer completeness from empty claim arrays, a false context flag, or
confidence values. Do not report source-read incompleteness when the reader
successfully returned the bounded complete file. Context insufficiency is a
model uncertainty report, not a completeness verdict.

## CLI, streams, and errors

- Proposed option: `--format text|json`; default remains `text`. Existing text,
  `--plain`, spinner, and exit behavior remain unchanged. In successful JSON
  mode, suppress the spinner and write exactly one UTF-8 JSON object plus
  newline to stdout, with no progress or prose.
- A `ForgeError` in JSON mode writes one safe v1 error envelope to stderr and
  leaves stdout empty. Keep ADR-0006 mapping: 1 `result_unavailable`, 2
  `input_unusable`, 3 `not_configured`, 4 `provider_failed`. Use the same
  generic safe messages already defined by the JSON contract; never serialize
  `str(error)` or provider/configuration data.
- Framework syntax, help, and parameter errors that happen before format
  selection retain their current text behavior. In text mode, preserve the
  existing diagnostic, stream, spinner, and exit behavior.

## Candidate decision record and owner decisions

If accepted, create a new ADR (candidate **ADR-0020: Add `forge explain` to
machine-readable JSON output**) before implementation. It should extend the
JSON command scope without rewriting ADR-0019's historical decision; ADR-0019
continues to describe the approved debug/inspect v1 scope at that time. The new
ADR should accept the explain schema, typed `processing_incomplete` signal,
stream/error behavior, privacy limits, and unchanged FR-7 / ADR-0006 behavior.

The owner should decide:

1. Whether `schema_version: 1` may add `command: "explain"` as a compatible
   additive command under the existing compatibility rule.
2. Whether the proposed `processing_incomplete` metadata and the separation of
   processing completeness from the existing `incomplete` flag are acceptable.
3. Whether `limitations` should expose the parsed statements as proposed, given
   they are untrusted model text, while excluding source excerpts and raw
   provider responses.
4. Whether existing `--plain` remains accepted (and redundant) in JSON mode or
   is rejected as a text-only option.

## Acceptance tests after approval

Use fake providers and temporary source files only; never call a live provider.
Deterministic tests must prove:

1. The envelope, field names, confidence enums, evidence kinds, inclusive line
   ranges, usage, model, safe relative path, and schema version match the
   accepted contract. Absolute paths and parent directories are not emitted.
2. Evidence is exactly the validated domain anchor; no source excerpt, source
   content, or unvalidated line range is serialized.
3. Diagnostics contain only section/category/count. Malformed and omitted
   claims are reflected as partial with the approved stable omission codes;
   no raw diagnostics, exceptions, prompt, provider response, secret, or
   environment value leaks.
4. Processing-incomplete true/false/unavailable maps to partial/complete/
   unknown. A context-insufficient-only result is complete with a warning and
   retains its separate uncertainty signal.
5. Success on TTY and piped output is exactly one parseable UTF-8 JSON line;
   no spinner/prose appears. ForgeErrors use one safe stderr error envelope,
   empty stdout, and unchanged exit codes 1-4.
6. Text remains the default and its rendered output, error messages, streams,
   `--plain`, and exit codes remain unchanged. Help and framework parameter
   errors remain usable without provider configuration.
7. A fake provider is called at most once with only the selected source; the
   serializer performs no filesystem, provider, environment, or Git access.

Until the owner approves this proposal and the candidate ADR, no explain JSON
implementation or runtime change is authorized.
