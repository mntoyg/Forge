# Proposed JSON output contract for `forge explain`

**Status: Accepted by the owner on 2026-11-05; implementation is staged under
[ADR-0020](../decisions/0020-explain-json-output.md).** This remains the
detailed schema reference. Stages A (parser metadata), B1 (pure serialization),
and B2 (CLI integration) are complete under that ADR.

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

`ExplanationResult.incomplete` is a legacy text-facing aggregate, not a JSON
completeness signal. The parser sets it for omitted claims and required fields,
but also for valid provider limitations, a retained claim whose invalid
confidence is downgraded to `possible`, context insufficiency, unsupported
source validation, and unavailable Python symbol-scope validation. Keep that
field and existing text rendering unchanged; do not copy it to
`completeness.status`.

Before implementation, add the proposed typed
`ExplanationResult.processing_incomplete: bool | None` plus two safe diagnostic
kinds, `SOURCE_VALIDATION_UNAVAILABLE` and
`SYMBOL_VALIDATION_UNAVAILABLE`. They close current parser paths that set
`incomplete` without a diagnostic when there are no claims to reject. The new
signal means **known parser omissions**, not semantic completeness:

- `true` means at least one claim or required response field was discarded or
  unavailable, with an omission diagnostic that gives a stable omission code.
- `false` means all required fields and submitted claims were handled and
  validated to the supported level. It does not mean the explanation is
  exhaustive or correct.
- `null` means validation availability prevents determining whether an
  omission occurred and no known omission already establishes `partial`.

Apply precedence: any known omission -> `partial`; otherwise unavailable
validation -> `unknown`; otherwise -> `complete`. This ensures every `partial`
result has at least one structured omission. Do not infer completeness from
empty claim arrays or confidence values. Context insufficiency and valid
limitations describe uncertainty/coverage caveats, not parser omissions.

### Diagnostic classification and stable objects

The following table covers every current `ExplanationDiagnosticKind`. The JSON
`result.diagnostics` keeps safe `{section, kind, count}` records. Completeness
warnings have exactly `{code, section}`; `section` is `purpose`, `flow`,
`symbols`, or null. Omission objects have exactly `{code, section, count}`;
`count` is the sum of corresponding typed diagnostic counts (diagnostic
occurrences, not claims or findings). Aggregate omissions by code and section.
Deduplicate warnings by code and section; sort both arrays by code, then
section (null first). No claim text, target, line, or model-supplied reason is
placed in these objects.

| Diagnostic kind | Classification | Completeness code / effect |
| --- | --- | --- |
| `SECTION_EMPTY` | Informational only | No warning or omission; an explicitly empty list is not a discarded claim. |
| `SECTION_MISSING`, `SECTION_MALFORMED` | Processing omission | `section_unavailable` with that section and combined count. |
| `CLAIM_MALFORMED` | Processing omission | `claim_unavailable` with section and count. |
| `SUBJECT_UNAVAILABLE` | Processing omission | `symbol_unavailable`, section `symbols`. |
| `EVIDENCE_MALFORMED`, `EVIDENCE_KIND_UNSUPPORTED`, `EVIDENCE_TARGET_SHAPE_UNSUPPORTED`, `EVIDENCE_TARGET_NOT_FOUND`, `EVIDENCE_SOURCE_SHAPE_MISMATCH`, `EVIDENCE_VALIDATION_UNAVAILABLE`, `CALL_TARGET_IS_DECLARATION`, `CALL_EXPRESSION_NOT_FOUND`, `SYMBOL_OPERATION_DISALLOWED`, `EVIDENCE_OUT_OF_SCOPE`, `PURPOSE_CALL_NOT_IN_FLOW` | Processing omission | `claim_evidence_unavailable` with section and combined count. These diagnostics arise when the associated claim is discarded. |
| `NAME_ONLY` | Processing omission | `symbol_description_unavailable`, section `symbols`. |
| `SYMBOL_ACTION_EVIDENCE_INSUFFICIENT` | Processing omission | `symbol_action_evidence_insufficient`, section `symbols`. |
| `CONFIDENCE_UNRECOGNIZED` | Non-omission warning | `confidence_downgraded`; the claim is retained as `possible`. |
| `LIMITATIONS_MISSING`, `LIMITATIONS_FIELD_MALFORMED` | Processing omission | `limitations_unavailable`, section null. |
| `LIMITATIONS_MALFORMED` | Processing omission | `limitation_entry_unavailable`, section null, count of invalid entries. |
| Non-empty typed `limitations` tuple | Non-omission warning | `limitation_present`, section null; wording may be parser-generated or provider-authored. |
| `CONTEXT_STATUS_MISSING`, `CONTEXT_STATUS_MALFORMED` | Processing omission | `context_status_unavailable`, section null. |
| `CONTEXT_INSUFFICIENT` | Non-omission warning | `context_insufficient`; never an omission by itself. |
| Proposed `SOURCE_VALIDATION_UNAVAILABLE` | Non-omission warning / availability signal | `source_validation_unavailable`; if no other omission exists, status is `unknown`. |
| Proposed `SYMBOL_VALIDATION_UNAVAILABLE` | Non-omission warning / availability signal | `symbol_validation_unavailable`; if no other omission exists, status is `unknown`. |

Valid non-empty `limitations` are not currently diagnostics. The proposed
`limitation_present` warning comes from this typed tuple; do not parse
limitation prose into codes or omissions. The tuple may include the parser's
generic context-limit statement as well as provider-authored statements, so
this code does not assert who supplied the wording. Unsupported non-Python
validation and Python tokenization failure set the new source-validation
diagnostic. Python syntax failure that prevents AST symbol-scope checks sets
the symbol-validation diagnostic. If an actual claim is discarded on either
path, its existing claim/evidence diagnostic still creates a known omission,
so the result is `partial`; the availability warning may also be present.

If `incomplete` is true but diagnostics are empty or consist only of
informational/warning kinds, do not invent a claim count or evidence. Emit
`unknown` when a proposed validation-availability diagnostic explains the
uncertainty; emit `complete` with warnings when only context, valid limitations,
or a retained downgraded-confidence claim explains the legacy flag. This
classification must be backed by the new typed signal and diagnostic kinds,
not inferred from `incomplete` or human-readable prose.

For symbol claims only, the parser applies a narrow structural guard to common
English coordinated-action forms where `and` may be followed by `then` before
a recognized action verb plus an explicit determiner. It requires one distinct
validated `(kind, target)` evidence anchor for each recognized coordinated
action plus one for the initial clause. Repeated anchors with the same kind and
target count once even when they cite different lines; different targets count
separately even when their ranges share a line. The guard compares counts; it
does not assign an anchor to a specific action. If the distinct-anchor count
falls short, the entire claim is omitted with
`SYMBOL_ACTION_EVIDENCE_INSUFFICIENT`. This deliberately bounded vocabulary
can miss other ways to combine actions. Distinct anchors still do not prove
semantic support or entailment. A noun phrase such as “source and request
metadata” is not treated as a second action unless it matches the
verb-plus-determiner form.

Examples (other envelope fields omitted):

For a context-insufficient-only result, legacy `result.incomplete` remains
true, while JSON completeness is `complete` with warnings because no parser
omission is known. The parser currently supplies a generic limitation
statement in this case, so both warning codes are present.

```json
{"completeness":{"status":"complete","warnings":[{"code":"context_insufficient","section":null},{"code":"limitation_present","section":null}],"omissions":[]}}
```

```json
{"completeness":{"status":"partial","warnings":[],"omissions":[{"code":"claim_evidence_unavailable","section":"flow","count":1}]}}
```

### Safe source path

The JSON path is always a deterministic, workspace-relative POSIX path derived
from the resolved selected file and the resolved invocation working directory
(the current `SourceReader` workspace). For a relative input, resolve it
against that workspace first; for an absolute input inside the workspace,
strip the workspace prefix by computing the relative path. Normalize separators
to `/` and reject any result that is empty, absolute, contains a drive prefix,
or has a `..` component. Compute this safe path before the use case/provider
call and pass it as typed presentation input; never fall back to the basename,
absolute path, workspace root, or parent path. If a safe relative path cannot
be derived, fail closed with the existing `input_unusable` error envelope and
exit code 2 before reading or calling the provider.

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

## Accepted decisions and implementation stages

The owner approved the additive `command: "explain"` under schema v1, the
typed `processing_incomplete` field and diagnostic mappings above, parsed
limitations, and keeping `--plain` accepted as a no-op in JSON mode. ADR-0020
records these choices while preserving ADR-0019 as the historical debug/
inspect decision. ADR-0020 also fixes the one-file/provider boundary, privacy,
stdout/stderr, safe-path, and unchanged exit-code requirements.

Stage A adds result metadata and parser diagnostics with deterministic tests;
presentation hides the new availability diagnostics to preserve text output.
Stage B1 adds the pure presentation serializer and deterministic unit tests.
Stage B2 wires `--format text|json` into the CLI, including the approved
success/error streams and end-to-end acceptance tests. Stages A, B1, and B2
are complete; explain JSON is available through the command option.

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

### Implementation handoff

Stages A and B1 are complete. Stage B2 adds the `forge explain --format
text|json` option and routes successful and Forge-error results through the
accepted serializers. Text remains the default, and `--plain` is redundant in
JSON mode. All three stages passed the repository quality gate; the detailed
CLI behavior is verified by deterministic fake-provider end-to-end tests.

The owner approval is recorded in ADR-0020. Stage A implements parser metadata
and deterministic tests while preserving existing text output. Stage B1 adds
the pure serializer. Stage B2 implements CLI format and error-stream
integration without changing the default text behavior.
