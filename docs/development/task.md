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

## Next feature: `forge explain <file>`

The roadmap calls for an explanation command that helps a developer understand
what a file does and why. This is the next feature to design; implementation
must wait until the owner accepts a concrete requirement and command contract.

### Small work breakdown

1. **SWE design task:** propose FR-7 and the smallest useful CLI contract. Define
   what an explanation contains, how it stays grounded in the selected file,
   source-size and provider-call limits, output and error behavior, and how the
   command reuses the existing safe reader and `AIProvider` port. Include
   acceptance criteria and deterministic fake-provider tests. Do not implement
   before the owner accepts the design.
2. **SWE implementation task, after approval:** implement only the accepted
   contract, add unit/integration/CLI tests at the appropriate levels, update
   user documentation, changelog, and project status, then run the full gate.
3. **Owner evaluation:** review the result and decide whether a live-provider
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
