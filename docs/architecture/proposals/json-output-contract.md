# Draft: machine-readable JSON output (FR-4.4)

**Status:** Draft for product-owner review. FR-4.4 remains deferred; this proposal is not approval to implement.

## Purpose and current behavior

FR-4.1 through FR-4.3 keep human-readable output as the default, send results to stdout and errors to stderr. FR-4.5 requires partial coverage to be disclosed. ADR-0006 defines exit codes; findings do not change them. ADR-0007's JSON is the provider's internal response format, not a Forge CLI contract. ADR-0012 (which supersedes ADR-0011) specifies when debug warns about possible partial coverage.

| Command | Result and diagnostics today | Error behavior |
| --- | --- | --- |
| `debug` / `debug --diff` | `AnalysisResult`: source path, findings, model/usage and optional file history. Whole-file safety warning is separate stderr text; diff is silent. Invalid individual provider findings may be discarded without a count in the result. | Typed input/config/provider failures map to ADR-0006 exit codes; error text to stderr. |
| `inspect` | `ProjectOverview`: root, guidance, languages, tools, checks, directories and prose omissions. Scanner completeness is not retained as a dedicated result field. | Typed input/config/provider failures use existing mapping; error text to stderr. |
| `review` | Before consent, a `ReviewPlan` is printed; after consent, `ReviewResult` has findings, typed path omissions and an incomplete flag. Non-TTY confirmation does not call provider. | No changes exits 1; decline exits 0; analysis errors use existing mapping. |
| `explain` | `ExplanationResult`: claims, source evidence, limitations, context-insufficient/incomplete flags and safe typed diagnostics. Successful incomplete results exit 0. | Errors to stderr with existing mapping. |

Human renderers and CLI orchestration currently own stream, TTY, spinner, consent and error presentation. Application result models are the source for a future serializer; do not serialize rendered prose or provider response text.

## Recommendation and scope

Recommend an explicit `--format json` option first for `forge debug` (including `--diff`) and `forge inspect`. These results are single-phase and map naturally to stable envelopes; debug covers findings and inspect provides useful deterministic repository facts. Keep text as default.

Exclude `review` initially: its plan-before-consent and post-consent result are two distinct phases, and a JSON consent protocol needs an owner decision. Exclude `explain` initially: its nested evidence/excerpts and safe diagnostics need a separate schema review. Add them only in later, independently reviewed scope.

Alternatives: (a) debug only, smallest compatibility surface but omits useful inspect output; (b) all four commands, uniform at launch but expands scope and forces decisions about review consent and explain evidence before needed. Owner approval is required for the recommendation and exclusions.

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

`status` is `success` or `error`. Successful `completeness.status` is `complete`, `partial`, or `unknown`. Complete means no known processing omission was reported; it does not mean the model found every issue or that its claims are correct. Warnings and omissions use stable codes and structured fields, not matching human prose. Keep counts/reasons only where the application has evidence for them. Never infer completeness from an empty findings list or claim a count of rejected AI claims when current result types do not provide one.

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

The `history` value, when present, contains its existing recent-commit records and window. `location` is null when absent. `mode` is `file` or `diff`. Do not expose prompt text, raw provider response, credentials, or unredacted environment/config values.

Example partial result: use a stable warning code for the known whole-file safety limit and set completeness to `partial`; for diff, do not invent that warning because current behavior is silent. For inspect, represent each known scanner omission with a code and safe relative path/details. Since current inspect result strings and underlying completeness are not fully typed in the result, implementation must preserve or add explicit safe metadata rather than parse prose. If completeness cannot be established, use `unknown`.

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
- Human output remains byte-for-byte behaviorally equivalent for existing cases, except help text documenting the option.
- Deterministic fake-provider/temp-directory tests cover debug with findings and no findings (both exit 0), file and diff modes, optional history/location, partial whole-file warning, inspect omissions/completeness, JSON TTY and pipe output, no progress/prose on stdout, safe errors on stderr with empty stdout, and unchanged exit mapping. Assert one parseable JSON object and no secrets, prompt, or raw provider text.
- No live provider call is needed for acceptance. Do not add `review` or `explain` support implicitly.

## Owner decisions required before implementation

1. Accept initial scope (`debug` + `inspect`) or choose debug-only/all four.
2. Accept `--format json`, its conflict with `--plain`, and text help/argument-error behavior.
3. Accept the envelope, `complete|partial|unknown` meaning, stable warning/error codes, and stderr JSON with empty stdout on command errors.
4. Decide whether to extend result types to preserve inspect completeness and count discarded debug claims; current types cannot report these reliably. Default recommendation: expose only evidence already represented and use `unknown` where necessary; do not add semantic-validation heuristics.
5. Confirm unchanged ADR-0006 exits and the exclusion of review consent and explain evidence in v1.

No accepted ADR needs to change if serialization remains a CLI/presentation concern, provider-internal JSON remains separate, and exit semantics stay unchanged. FR-4.4 remains deferred until owner acceptance.

## Post-approval implementation breakdown

1. Record owner choices; update FR-4.4 and add/adjust a decision record if the accepted public contract requires it. Stop if an ADR conflict is unresolved.
2. Add the CLI format option and a presentation-layer serializer/envelope; preserve text and existing exit mapping.
3. Add only owner-approved result metadata for completeness/omissions, then wire debug and inspect serialization.
4. Add deterministic fake/temp-repository tests, user docs, changelog/status updates; run the full gate and review the diff before delivery.
