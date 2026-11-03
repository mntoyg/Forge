# Draft proposal: `forge explain <FILE>`

**Status:** Draft for project-owner review. This proposal does not approve
implementation or change `docs/product/requirements.md`.

## Proposed user outcome and contract

A developer invokes `forge explain <FILE>` to understand an unfamiliar source
file without leaving the terminal. Forge returns a concise account of the
file's apparent purpose, important symbols, and main input/control/data flow.
It explains *why* only when the supplied code supports that inference; it must
label inferred intent and say when the reason is not knowable from this file.

Proposed FR-7 (for owner approval):

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
  cite one-based line ranges in the supplied file. Validate ranges against the
  source snapshot and render any excerpts from that snapshot, not from model
  quotes. Drop claims with invalid or absent evidence and mark the result
  incomplete. Label uncertainty and state when this file alone does not
  establish purpose or behavior.
- **FR-7.5:** Remain read-only: do not modify files, execute source or
  repository commands, discover adjacent files, retry with more context, or
  start an autonomous loop. Treat source and provider output as untrusted data.

Suggested command: `forge explain <FILE> [--plain]`, with an explicit single
file path. `--plain` follows `debug`; otherwise stdout uses plain text when it
is not a TTY, per FR-4.2. Errors go to stderr. Help remains available without
an API key. An invocation explicitly selecting a file is proposed as consent
for one provider call, matching `forge debug`; do not add an interactive
confirmation gate that would make piped use behave differently. Show a spinner
only on a TTY stderr while the call is running.

## Evidence, cost, and limits

The application should request a compact structured answer (for example,
purpose, key symbols/flow, and limitations), using the existing
`CompletionRequest` and defensive parsing conventions. Each claim carries one
or more line ranges. The renderer attaches source excerpts by looking them up
in the validated snapshot. A model's explanation is an interpretation, not a
fact; citations establish where the interpretation came from, not that it is
correct. Repository comments or strings that look like instructions remain
untrusted source data.

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

**Safe-reader implementation note:** the current filesystem reader checks
`stat().st_size` and then calls `read_bytes()`. That leaves a growth window
between the check and the read. Before this command ships, preserve the existing
limit while bounding the actual read (for example, read at most the limit plus
one sentinel byte), refuse overflow without truncation, and test a file that
grows after the size check. This closes the existing FR-3.4 boundary; it does
not require a new product limit.

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
3. Missing, directory, outside-workspace/symlink escape, empty, invalid UTF-8,
   and over-limit inputs fail before a provider call. A growth-after-size-check
   test proves the actual read remains bounded, refuses rather than truncates,
   and makes zero provider calls.
4. A provider context-length failure makes one call at most, reports an
   actionable error with exit code `4`, and triggers no retry or chunking.
5. CLI tests cover help without a key, missing configuration (`3`), success
   and provider errors, output streams, plain output without a TTY, and absence
   of repository execution or file writes.

## Decision boundary

**ADR recommendation: no new ADR for this MVP.** A one-file use case reuses the
accepted `SourceReader`, `AIProvider`, layer boundaries, and exit-code contract;
this proposal adds no dependency, persistence, or concurrency. The owner must
approve FR-7 and the command contract before they are added to the requirements
or implemented. A dollar-price promise, multi-file context, retries/chunking,
or any new provider/architecture boundary needs a separate product decision and
possibly an ADR. In particular, do not revive ADR-0013's suspended windowing
approach.
