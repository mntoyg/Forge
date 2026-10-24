# ADR-0014 - Bounded multi-file change review

## Status

Accepted - 2026-10-24

## Context

`forge debug <file> --diff` reviews one file against `HEAD`, with changed lines
marked in the full current file. ADR-0008 deliberately deferred sweeping every
changed file because provider calls and cost would multiply. Phase 4 of the
roadmap calls for a separate `forge review` command. It can provide one
cross-file view without changing the single-file debug contract, but its
multi-file input, secret handling, cost, and locations need explicit limits.

The suspended ADR-0013 does not provide a safe long-file strategy: measured
300- and 800-line marked windows missed defects at their ends. The new command
must not use those windows or claim complete model coverage.

## Decision

Add a separate, human-controlled `forge review [PATH ...]` use case. This ADR
accepts its design; implementation remains subject to its requirements and
tests.

- With no paths, scope the working tree against `HEAD`: combine staged and
  unstaged changes and include non-ignored untracked files. Explicit paths
  narrow this set. Resolve the Git worktree root even when invoked in a
  subdirectory; user paths are relative to the current directory and must stay
  inside that root.
- Create a local snapshot and plan before consent. Show included and omitted
  paths, configured model, UTF-8 request bytes, a clearly approximate token
  estimate, and that at most one billable provider call will occur. Ask for
  confirmation in a TTY. Without a TTY, show the plan and make no provider
  call. After consent, submit the same snapshot that was planned.
- Permit at most one provider call per invocation. Group full current text
  files in one request, with real line numbers and changed lines marked as in
  ADR-0008. The combined UTF-8 byte length of all completion message contents
  must not exceed **16,000 bytes** and the response limit is **1,000 output
  tokens**. If the request exceeds the
  byte cap, make no provider call and ask the user to narrow the paths. The
  byte cap bounds payload size; it does not promise model coverage or an exact
  price. Report actual token usage returned by the provider after a run.
- Preserve `forge debug --diff` as a one-file command. The new aggregate
  request does not use the ADR-0013 windows. Always describe the result as an
  AI review that may miss defects; list known omissions and do not claim that
  submitted files were comprehensively reviewed.
- Abort the whole invocation before provider submission if a requested file
  matches a known sensitive-path rule or a supported inline-secret pattern.
  Do not print or log matched values. Detection is heuristic and cannot
  guarantee discovery of arbitrary secrets; the plan must say that source is
  sent to the configured provider after consent.
- Skip and report deletion-only paths, binary files, symlinks, and ignored
  untracked files. Tracked files remain eligible even if they match an ignore
  rule. A rename recognized by Git is displayed as `old -> new` and analyzed
  at its current destination; if Git does not recognize it, report the delete
  and addition separately. Known omissions make the result visibly
  incomplete. Do not read the contents of ignored paths.
- Findings must name a normalized repository-relative path and a one-based
  line in that path's planned current snapshot. Accept only paths in the
  submitted manifest and lines marked changed for that path. Render evidence
  excerpts from the validated snapshot, not from a model-supplied quote. Drop
  invalid findings and mark the response incomplete. Keep Git facts distinct
  from model conclusions.
- Use the existing `AIProvider` and safe source-reading boundary, plus a
  narrow Git change-set port and adapter. Keep GitPython in infrastructure,
  parsing in application, Typer in `cli/`, rendering in `presentation/`, and
  wiring in `main.py`. GitPython may perform read-only Git queries; Forge must
  not run project scripts, checks, hooks, or commands derived from repository
  content. Add no dependency, write no user files, and run no autonomous loop.

The current exit-code contract remains: `0` for a completed review or a user
cancellation, `1` when no result can be produced (including a non-TTY run),
`2` for an unusable scope or a request over the cap, and existing configuration
and provider codes for those failures. Findings do not change the exit code.

## Alternatives considered

- **One call per file:** simpler per-file prompts, but cost grows with changed
  file count and exceeds the accepted one-call budget.
- **Raw multi-file diff:** smaller input, but removes surrounding context and
  makes reliable current-file locations harder, the same reasons ADR-0008
  rejected raw diffs.
- **Window long files:** rejected; ADR-0013 remains suspended without a new
  measurement and a superseding decision.
- **Read deleted blobs:** can find regressions caused by removals, but its
  locations refer to a base revision rather than the current file. Deferred
  until a separate product decision and explicit old-revision location type.

## Consequences

The call count and request bytes are bounded before provider use, scope is
visible before consent, and existing single-file behavior stays stable. A
single model request spanning files has not been measured for review quality;
the cap is a cost/input bound, not evidence of complete attention. Secret
pattern checks can have false positives and false negatives. Deleted code is
not analyzed. These limitations must remain visible in output and user docs.
