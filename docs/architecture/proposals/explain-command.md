# Accepted contract: `forge explain <FILE>`

**Status:** Approved by the project owner on 2026-11-04 and implemented under
FR-7. This document remains the accepted command contract.

## Proposed user outcome and contract

A developer invokes `forge explain <FILE>` to understand an unfamiliar source
file without leaving the terminal. Forge returns a concise account of the
file's apparent purpose, important symbols, and main input/control/data flow.
It explains *why* only when the supplied code supports that inference; it must
label inferred intent and say when the reason is not knowable from this file.

FR-7:

- **FR-7.1:** Explain one user-selected source file, with no automatic scan of
  other files, Git history, or project commands.
- **FR-7.2:** Read through the existing `SourceReader` boundary. Require a
  regular, non-empty UTF-8 file resolved inside the current workspace. Enforce
  the existing `FORGE_MAX_FILE_BYTES` setting (default **200,000 bytes**);
  reject over-limit input without truncating it.
- **FR-7.3:** Use at most one call to the configured `AIProvider` per
  invocation. Tell the user the selected file is sent to that provider; never
  log the source or the full prompt. Do not claim an exact dollar cost.
- **FR-7.4:** Return a human-readable explanation whose substantive claims
  cite typed evidence anchors in the supplied file. Each anchor carries a kind,
  an exact source target, and an inclusive one-based line range. For `.py` and
  `.pyi`, validate ranges, exact target tokens, and kind-specific shape using
  Python's standard tokenizer; comment and string tokens cannot satisfy an
  anchor. Symbol roles require call, access, return-type, or return-value
  anchors, so imports, constructor assignments, or closing delimiters alone
  cannot support such a role. Each symbol claim names its exact declared
  subject in a `symbol` field. The subject must resolve to one class, function,
  or async function declaration, and every cited range must be inside that
  declaration's AST scope. Duplicate, unsupported, missing, and out-of-scope
  subjects are omitted and make the result incomplete. Other extensions remain
  valid inputs, but their evidence claims are omitted and the result is marked
  incomplete. These structural checks do not prove semantic entailment. Label
  uncertainty and state when this file alone does not establish purpose or
  behavior.
- **FR-7.5:** Remain read-only: do not modify files, execute source or
  repository commands, discover adjacent files, retry with more context, or
  start an autonomous loop. Treat source and provider output as untrusted data.
- **FR-7.6:** A Purpose claim with call evidence must include at least one call
  anchor exactly equal by kind, target, start line, and end line to a call
  anchor in a Main flow claim that independently passed validation. Validate
  Main flow before Purpose internally, without changing render order. If no
  validated Main flow call anchor matches, omit the Purpose claim and mark the
  result incomplete. Invalid Purpose evidence retains its existing specific
  diagnostic.

Suggested command: `forge explain <FILE> [--plain]`, with an explicit single
file path. `--plain` follows `debug`; otherwise stdout uses plain text when it
is not a TTY, per FR-4.2. Errors go to stderr. Help remains available without
an API key. An invocation explicitly selecting a file is proposed as consent
for one provider call, matching `forge debug`; do not add an interactive
confirmation gate that would make piped use behave differently. Show a spinner
only on a TTY stderr while the call is running.

## Evidence, cost, and limits

The application requests a compact structured answer (purpose, key
symbols/flow, and limitations) using the existing `CompletionRequest` and
defensive parsing conventions. Each evidence item has `kind`, `target`,
`start_line`, and `end_line`. Supported kinds are `call`, `access`,
`return_type`, `return_value`, and `operation`. For `.py` and `.pyi`, use the
standard Python tokenizer to check exact target tokens and source shape: calls
must be actual call expressions, return types follow `->`, return values occur
in an explicit `return` expression, and accesses are not import sites or
assignment left-hand sides. Comment and string tokens cannot match. Each symbol
claim includes an exact `symbol` name resolving to one class/function
declaration in the same AST. All symbol evidence ranges must be within that
declaration's source scope. Symbol claims cannot use generic `operation`
anchors. Other extensions remain readable inputs, but their claims are omitted
and the result is marked incomplete. The renderer attaches excerpts from the
validated snapshot. A model's explanation is an interpretation, not a fact;
these checks validate location and structure, not semantic entailment.
Repository comments or strings that look like instructions remain untrusted
source data.

The smallest proposal sends the full selected file in one request, with no
chunking, windows, or second call. The byte ceiling is the existing configured
source limit, not a guarantee that every selected model can fit the prompt.
There is no reliable provider-independent dollar estimate. The result should
identify the configured model and report actual token usage when returned by
the provider. If the source does not contain callers, configuration, or other
needed context, the answer must say so instead of guessing. Do not claim full
semantic coverage.

If the provider rejects the request for context length, return an actionable
provider error (existing exit code `4`) without retrying, truncating, or
splitting the file. If a valid response says the supplied file is insufficient
to explain a behavior, render that limitation as part of the result; a valid,
limited explanation is still a completed command. No new secret scanner is
proposed here: the selected source is sent after invocation, so help and user
documentation must say that plainly. Never print detected credential values
if a future decision adds secret detection.

**Safe-reader implementation note:** the filesystem reader checks the size and
then reads at most the configured limit plus one sentinel byte. It refuses
overflow rather than truncating, including when a file grows between the check
and read. Deterministic integration tests verify the bound and that no provider
call occurs on overflow.

## Errors and exit codes

Keep ADR-0006's public mapping: `0` for a usable explanation even if it lists
uncertainty; `1` when no valid result can be produced; `2` for a missing,
unreadable, empty, non-text, outside-workspace, or over-limit file; `3` for
missing/invalid configuration; and `4` for a provider failure. Findings or
interpretations do not change the exit code. No new exit code is proposed.

## Architecture and deterministic acceptance tests

Wire a narrow `ExplainSource` application use case with the existing
`SourceReader` and `AIProvider` ports. Keep provider construction in
`infrastructure/`, Typer in `cli/`, parsing in `application/`, rendering in
`presentation/`, and wiring in `main.py`. Reuse the existing source and
configuration limits; add no dependency and no provider-specific field to
`AIProvider`.

Acceptance criteria and fake-provider tests:

1. A temporary source file produces the specified prompt, exactly one fake
   provider call, line citations that point to the submitted snapshot, and
   human-readable output; uncertain intent is labeled.
2. Fake responses with valid, out-of-range, reversed, or missing evidence
   ranges prove validation and visible incomplete/unsupported context behavior.
   Symbol tests also prove a unique declared subject with in-scope use sites is
   rendered, while unrelated, undeclared, duplicate, out-of-scope, and
   name-only symbol claims are omitted and marked incomplete.
3. Missing, directory, outside-workspace/symlink escape, empty, invalid UTF-8,
   and over-limit inputs fail before a provider call. A growth-after-size-check
   test proves the actual read remains bounded, refuses rather than truncates,
   and makes zero provider calls.
4. A provider context-length failure makes one call at most, reports an
   actionable error with exit code `4`, and triggers no retry or chunking.
5. CLI tests cover help without a key, missing configuration (`3`), success
   and provider errors, output streams, plain output without a TTY, and absence
   of repository execution or file writes.
6. A Purpose call anchor survives only when it exactly matches an independently
   validated Main flow call anchor. A valid but unmatched call, or no validated
   Main flow call, omits Purpose with a fixed safe diagnostic while preserving
   valid flow and symbol claims. Malformed or otherwise invalid Purpose evidence
   keeps its more specific existing diagnostic.

## Decision boundary

**ADR-0015** accepts the explicit symbol subject and Python AST scope check.
**ADR-0016** binds Purpose call evidence to an independently validated Main
flow call anchor. It does not compare claim prose or prove semantic entailment.
The one-file use case still reuses the accepted `SourceReader`, `AIProvider`,
layer boundaries, and exit-code contract; no dependency, persistence, or
concurrency is added. FR-7 and the command contract were approved before
implementation. A dollar-price promise,
multi-file context, retries/chunking,
or any new provider/architecture boundary needs a separate product decision and
possibly an ADR. In particular, do not revive ADR-0013's suspended windowing
approach.
