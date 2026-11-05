# Forge Feature Plan

**Updated:** 2026-11-05

**Purpose:** Keep the next user-facing feature and its handoff sequence clear for
the project owner and the Codex SWE.

## Product goal

Make Forge a trustworthy, read-only terminal assistant that helps developers
understand unfamiliar code and debug or review real repositories. It should be
safe, bounded, evidence-based, transparent about uncertainty, and useful from a
terminal without requiring an IDE.

## Delivered capabilities

- `forge debug <file>` analyzes one file through the configured AI provider.
- `forge debug <file> --diff` focuses analysis on changed lines and can attach
  Git history to findings.
- `forge inspect [directory]` summarizes bounded local project evidence without
  calling a provider or executing project commands.
- `forge review [PATH ...]` reviews a bounded working-tree change set after
  confirmation, with at most one provider call and explicit omissions.

## Delivered feature: `forge explain <file>`

The owner-approved FR-7 contract in
`docs/architecture/proposals/explain-command.md` is implemented as a
single-file capability. Keep future work within its accepted scope.

### Small work breakdown

1. **Owner evaluation:** review the result and decide whether a live-provider
   quality check is worth its cost. Automated tests must never call a live
   provider.

### Boundaries

- Read-only: do not modify user files, execute repository code, or start an
  autonomous loop.
- Keep the Clean Architecture dependency direction and use the existing
  provider boundary; no dependency or architecture changes without an ADR.
- Explain only what the supplied evidence supports and show uncertainty or
  missing context honestly.

## Following feature: machine-readable output

The owner-approved FR-4.4 v1 scope and Phase 1 metadata are recorded in
[ADR-0019](../architecture/decisions/0019-json-output-phase-1-metadata.md).
The detailed contract remains in
[`json-output-contract.md`](../architecture/proposals/json-output-contract.md).
Phase 1 adds typed parser and scan completeness metadata only; it does not add
JSON output or change text behavior.

### Phase 2 — JSON serialization and CLI format

Add the approved JSON format option and serializer for `debug` (including
`--diff`) and `inspect`. Preserve text as the default, existing exit codes, and
stdout/stderr boundaries. Add deterministic tests for success, errors, and
completeness mapping. `review` and `explain` remain excluded from v1.

## Deferred research: full review of long files

ADR-0013 is suspended because measured marked windows missed findings near the
end. Do not implement a windowing strategy until the required attention test is
run and a new ADR is accepted.

## Release actions

- `mntoyg/Forge` is public as of 2026-11-04. Keep `mntoyg/Forge-archive`
  private.
- `v0.1.0` is published to GitHub Releases and PyPI through Trusted Publishing.
- The owner verified the install with `uvx --from mntoyg-forge==0.1.0 forge
  --version`, which returned `forge 0.1.0`.
