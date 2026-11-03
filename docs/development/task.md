# Forge Feature Plan

**Updated:** 2026-11-04

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

After `forge explain`, define and implement the deferred FR-4.4 JSON output and
shared presentation behavior across commands. First agree on the output
contract; keep human-readable output as the default.

## Deferred research: full review of long files

ADR-0013 is suspended because measured marked windows missed findings near the
end. Do not implement a windowing strategy until the required attention test is
run and a new ADR is accepted.

## Release actions

- `mntoyg/Forge` is public as of 2026-11-04. Keep `mntoyg/Forge-archive`
  private.
- Tagging `v0.1.0` remains a deliberate owner action after release preflight and
  green CI. PyPI publishing remains out of scope.
