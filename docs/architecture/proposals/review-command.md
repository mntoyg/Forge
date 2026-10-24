# Proposal: `forge review`

**Status:** Accepted for implementation by [ADR-0014](../decisions/0014-bounded-multi-file-change-review.md).
Implementation has not started.

## User outcome and existing behavior

A developer preparing a change wants one evidence-backed pass across related
files, with findings tied to the changed lines and a clear account of what was
sent. `forge review` would add a repository change set and cross-file context to
the answer.

Today, `forge debug <file> --diff` analyzes one named file. It compares the
working tree with `HEAD` (staged and unstaged together), sends that whole file
with changed lines marked, and scopes findings to those lines. An untracked
file is treated as entirely new. A deletion-only file has no current lines to
analyze. The command does not sweep other changed files. `forge inspect` is a
bounded, local overview of allowlisted project metadata; it neither reads
source for review nor calls a provider. The new command must not duplicate
either command's purpose.

## Proposed MVP

- Invoke `forge review [PATH ...]` from a Git worktree. With no paths, plan to
  review all eligible changes against `HEAD`; optional paths narrow that set.
  The set includes staged and unstaged tracked changes together, plus
  non-ignored untracked files. Show the resolved list and request interactive
  confirmation before sending any source to the configured provider. In a
  non-interactive session, print the plan and make no provider call.
- Make at most **one provider call per invocation**. Send eligible current
  file contents with real line numbers and changed lines marked, using the
  ADR-0008 representation, grouped by path. Do not send a raw unified diff.
  Show the configured model, file count, changed-line count, and an explicitly
  approximate input-token estimate before confirmation; do not claim a dollar
  price without reliable provider pricing data.
- Set a deterministic aggregate context limit of 16,000 UTF-8 bytes across
  completion message contents and cap output at 1,000 tokens. If the
  requested set exceeds it, do not truncate, split into more calls, or call the
  provider; list the scope and ask the user to narrow paths. Report files
  excluded for known limits in the result. A submitted file list is evidence
  of input scope, not proof that a model found every defect.
- Detect renames and show `old -> new`; analyze the current destination when it
  has changed lines. Deletion-only paths have no current source and are listed
  as not analyzed. Skip binary files and Git-ignored files, and identify these
  exclusions in the plan/result. Do not read ignored files just to report them.
- Abort the entire invocation before provider submission when a selected path
  matches a known sensitive-path rule or supported inline-secret pattern.
  Never print or log matched values. Detection is heuristic and cannot promise
  to find arbitrary secrets; tests must prove recognized patterns abort.
- Require each finding to identify a submitted path and a real line in that
  path's current snapshot, on a changed line, with a concise evidence excerpt
  or a direct explanation of the observed change. Validate path and line
  against submitted inputs; discard invalid locations and disclose that the
  response was incomplete. Keep model conclusions distinguishable from Git
  facts. Render shared findings through `presentation/`.
- The command only reads repository state and source. It does not modify files,
  execute repository commands, run checks, or continue an autonomous loop.

## CLI alternatives

| Contract | Trade-off |
| --- | --- |
| `forge review` reviews all eligible working-tree changes and confirms the displayed plan | Convenient for the common case; broad context can exceed the cap and must stop before a provider call. |
| `forge review --staged` reviews only the index | Smaller and commit-oriented; excludes unstaged work and untracked files unless separately selected. |
| `forge debug --diff` without a path sweeps the working tree | Reuses an existing verb but silently changes ADR-0008's single-file contract and confuses focused debugging with change review. |

**Recommendation:** a separate `forge review [PATH ...]`, defaulting to all
eligible changes with a confirmation after the scope preview. Keep stage
selection and base-ref comparison out of the first version; add them only if
users need them. Preserve `forge debug --diff` unchanged.

## Architecture and decision boundary

Use a `ReviewChanges` application use case, `AIProvider` and `SourceReader`
ports, and a narrow Git-backed change-set port/adapter in `infrastructure/`.
Keep Typer parsing in `cli/`, rendering in `presentation/`, and wiring in
`main.py`; use no new dependency. Repository instructions and source are
untrusted data. Existing path containment, size checks, provider error
translation, and exit-code ownership remain applicable; the proposed secret
filtering must be designed and tested for this use case.

ADR-0014 accepts a new Git change-set port for this separate command; it does
not alter the one-file `debug --diff` contract in ADR-0008. Do not use the
suspended ADR-0013 windows or claim long-file completeness. An over-limit
review stops before the provider call rather than windowing files.

## Acceptance criteria and deterministic tests

- A temporary Git repository with staged, unstaged, and untracked text changes
  produces one correctly combined scope and exactly one fake-provider call.
- Explicit paths narrow the scope; a clean repository and a path outside the
  worktree produce actionable errors without provider calls.
- Rename, deletion-only, binary, ignored, sensitive-path, and recognized
  inline-secret cases follow the rules above; fake-provider inputs and captured
  output contain no recognized secret value.
- An aggregate-limit case makes zero provider calls, names the omitted scope,
  and asks for narrower paths; no content is silently truncated or split.
- Fake findings with valid, unchanged-line, out-of-range, and unknown-path
  locations prove validation and incomplete-result reporting.
- CLI tests prove the plan is shown before confirmation, decline makes no
  provider call, non-interactive invocation makes no provider call, and the
  command never writes files or executes checks.

## Decisions to make before implementation

**Accepted defaults:** a detected secret aborts the invocation; scope and
budget are previewed for confirmation, with non-TTY invocations making no
provider call; deleted-file contents remain out of scope.

**Engineering:** Which GitPython status/diff representation reliably captures
staged plus unstaged state and renames across supported platforms? How will the
provider-independent token estimate be calibrated and labeled? Can the
existing finding/parser model carry a validated path without weakening current
single-file location guarantees?
