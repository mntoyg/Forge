# Machine-readable JSON output contract (FR-4.4)

**Status:** Owner-approved v1 direction and detailed schema reference. Phase 1 result metadata is recorded in ADR-0019. JSON serialization and CLI format options remain Phase 2; FR-4.4 stays deferred until that user-facing mode is implemented.

## Purpose and current behavior

FR-4.1 through FR-4.3 keep human-readable output as the default, send results to stdout and errors to stderr. FR-4.5 requires partial coverage to be disclosed. ADR-0006 defines exit codes; findings do not change them. ADR-0007's JSON is the provider's internal response format, not a Forge CLI contract. ADR-0012 (which supersedes ADR-0011) specifies when debug warns about possible partial coverage.

| Command | Result and diagnostics today | Error behavior |
| --- | --- | --- |
| `debug` / `debug --diff` | `AnalysisResult`: source path, findings, model/usage, optional history, and Phase 1 `incomplete` flag for discarded parser entries (no count). Whole-file safety warning is separate stderr text; diff is silent. | Typed input/config/provider failures map to ADR-0006 exit codes; error text to stderr. |
| `inspect` | `ProjectOverview`: root, guidance, languages, tools, checks, directories, prose omissions, and Phase 1 `scan_complete` copied from `ProjectEvidence.complete`. | Local path/filesystem failures are caught as `ForgeError`, printed to stderr, and mapped by the existing CLI exit-code function. `inspect` does not call a provider or require provider configuration. |
| `review` | Before consent, a `ReviewPlan` is printed; after consent, `ReviewResult` has findings, typed path omissions and an incomplete flag. Non-TTY confirmation does not call provider. | No changes exits 1; decline exits 0; analysis errors use existing mapping. |
| `explain` | `ExplanationResult`: claims, source evidence, limitations, context-insufficient/incomplete flags and safe typed diagnostics. Successful incomplete results exit 0. | Errors to stderr with existing mapping. |

Human renderers and CLI orchestration currently own stream, TTY, spinner, consent and error presentation. Application result models are the source for a future serializer; do not serialize rendered prose or provider response text.

## Recommendation and scope

The owner-approved v1 scope is `forge debug` (including `--diff`) and `forge inspect`, with human-readable text as the default. These single-phase results map naturally to stable envelopes; debug covers findings and inspect provides useful deterministic repository facts.

The owner-approved scope excludes `review`: its plan-before-consent and post-consent result are two distinct phases, and a JSON consent protocol would widen the contract. It also excludes `explain`, whose nested evidence, excerpts, and safe diagnostics require separate scope. Any later expansion needs independent review.

Alternatives considered: (a) debug only, with the smallest compatibility surface but no inspect output; (b) all four commands, with uniform launch support but additional review-consent and explain-evidence decisions. The owner selected debug and inspect for v1; review and explain are excluded.

## Proposed CLI and stream contract

- `--format text|json`; default `text`. `--plain` remains a text-rendering option and conflicts with `--format json` (argument error). JSON works on TTYs and pipes identically.
- A successful command writes exactly one UTF-8 JSON object followed by newline to stdout. No spinner, Rich markup, progress, or prose is written to stdout in JSON mode. Suppress progress UI in JSON mode; any diagnostic warning belongs in the JSON envelope.
- A command failure writes one safe JSON error object to stderr and nothing to stdout. Preserve ADR-0006 exit codes: 0 usable result (including zero findings), 1 no usable result/provider response, 2 unusable input, 3 not configured, 4 provider failure. Findings never affect exit status. Syntax/help errors that occur before format selection may retain the CLI framework's existing text behavior; confirm this edge with the owner.
- In text mode, preserve all existing output, TTY, warning, consent, and exit behavior.

## Version 1 envelope

```json
{
  "schema_version": 1,
  "command": "debug",
  "status": "success",
  "result": {},
  "completeness": {
    "status": "complete",
    "warnings": [],
    "omissions": []
  }
}
```

`status` is `success` or `error`. Successful `completeness.status` is `complete`, `partial`, or `unknown`. `complete` means the declared bounded processing scope completed without a known omission; it does not mean the model found every issue or that its claims are correct. `partial` requires affirmative evidence of an omitted part of that scope. `unknown` means current result metadata cannot establish whether such an omission occurred. Warnings and omissions use stable codes and structured fields, not matching human prose. Keep counts/reasons only where the application has evidence for them. Never infer completeness from an empty findings list or claim a count of rejected AI claims when current result types do not provide one.

Example debug result (field names are proposed):

```json
{
  "schema_version": 1,
  "command": "debug",
  "status": "success",
  "result": {
    "path": "src/app.py",
    "mode": "diff",
    "findings": [{
      "summary": "Unchecked value can be null",
      "detail": "The value is dereferenced without a preceding check.",
      "severity": "medium",
      "confidence": "likely",
      "location": {"line": 42}
    }],
    "history": null,
    "model": "configured-model",
    "usage": {"input_tokens": 1200, "output_tokens": 180}
  },
  "completeness": {"status": "complete", "warnings": [], "omissions": []}
}
```

This example assumes Phase 2 serialization sees `AnalysisResult.incomplete == false` and no whole-file size caveat. `complete` means no known processing omission within the declared scope, not that the model found every issue. The `history` value, when present, contains its existing recent-commit records and window. `location` is null when absent. `mode` is `file` or `diff`. Do not expose prompt text, raw provider response, credentials, or unredacted environment/config values.

### Completeness using current data and proposed metadata

- **Debug:** Phase 1 adds `AnalysisResult.incomplete`, true if parsing discarded one or more raw entries, with no count. Emit `partial` if this flag is true or `_size_warning` applies to the whole-file run. Otherwise emit `complete` within the declared scope. ADR-0012 still suppresses the size caveat for `--diff`; parser omissions can still make a diff result partial. Never infer completeness from an empty findings list or imply AI coverage/correctness.
- **Inspect:** Phase 1 adds `ProjectOverview.scan_complete`, copied from `ProjectEvidence.complete`. Emit `partial` when false and `complete` when true, describing only completion of the bounded scan. Bounded exclusions and selected metadata scope do not claim that every repository file was read. `inspect` remains local and has no provider/configuration failure mode.
- Use `unknown` only when the relevant typed signal is unavailable. Represent known partial conditions with stable warning/omission codes and safe relative paths where available. Do not parse prose to determine completeness or expose finding rejection counts.

Example error (stderr; stdout empty; exit code remains the ADR-0006 value):

```json
{
  "schema_version": 1,
  "command": "debug",
  "status": "error",
  "error": {"code": "input_unusable", "message": "The selected source could not be read."}
}
```

Use stable error codes such as `result_unavailable`, `input_unusable`, `not_configured`, and `provider_failed`; keep messages safe and concise. The code is descriptive and does not replace the exit code.

## Compatibility and acceptance criteria

- `schema_version` is an integer major version. Within v1, field removal/rename, type changes, enum meaning changes, or changed stream/exit semantics are breaking changes and require a new major schema version and owner review. Additive fields and new command/error/warning codes are allowed; consumers should ignore unknown fields/codes.
- Use UTF-8, snake_case keys, stable lower-case enum values, ISO dates, and workspace-relative paths where available. Never promise that AI findings are complete or proven by citations.
- For `inspect`, `result.root` is the selected project's final directory name, not its absolute local path. It identifies the selected root without exposing parent directories; callers needing globally unique identity should combine it with their own repository context.
- Human output remains byte-for-byte behaviorally equivalent for existing cases, except help text documenting the option.
- Deterministic fake-provider/temp-directory tests cover debug with findings and no findings (both exit 0), file and diff modes, optional history/location, partial whole-file warning, inspect omissions/completeness, JSON TTY and pipe output, no progress/prose on stdout, safe errors on stderr with empty stdout, and unchanged exit mapping. Assert one parseable JSON object and no secrets, prompt, or raw provider text.
- No live provider call is needed for acceptance. Do not add `review` or `explain` support implicitly.

## Phase 2 implementation notes

The owner-approved scope, text default, completeness meanings, and Phase 1
metadata are fixed by ADR-0019. Phase 2 adds the proposed `--format json`
surface and serializer only for debug and inspect. Preserve the ADR-0006 exit
mapping and text behavior; keep errors on stderr and results on stdout. Before
implementation is considered complete, review exact error/warning codes and
ensure completeness is derived from the typed fields above, never rendered
prose. `review` and `explain` remain excluded from v1.

No accepted ADR needs to change if serialization remains a CLI/presentation concern, provider-internal JSON remains separate, and exit semantics stay unchanged. FR-4.4 remains deferred until the user-facing JSON mode is implemented.

Phase 2B1 wires `--format text|json` to successful `debug` and `inspect`
results. In this interim phase, errors keep their existing text diagnostics and
ADR-0006 exit mapping; JSON error envelopes and their stderr behavior are
Phase 2B2. FR-4.4 remains incomplete until Phase 2B2 is delivered.

## Post-approval implementation breakdown

1. Record owner choices; update FR-4.4 and add/adjust a decision record if the accepted public contract requires it. Stop if an ADR conflict is unresolved.
2. Add the CLI format option and a presentation-layer serializer/envelope; preserve text and existing exit mapping.
3. Add only owner-approved result metadata for completeness/omissions, then wire debug and inspect serialization.
4. Add deterministic fake/temp-repository tests, user docs, changelog/status updates; run the full gate and review the diff before delivery.
