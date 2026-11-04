# ADR-0016 - Bind provider-backed Purpose evidence to Main flow

## Status

Accepted - owner approval on 2026-11-04

## Context

FR-7 validates each explanation anchor against the submitted source snapshot.
That check does not establish that a provider-backed Purpose claim points to
the same provider invocation described in Main flow. Prompt guidance alone did
not prevent a Purpose claim from using a different target or line range, which
caused an otherwise useful Purpose claim to be omitted.

The validator must make this relationship deterministic without interpreting
free-text claims or weakening the existing source, token, and AST checks. It
must also keep diagnostics free of provider-controlled text and preserve the
presentation order of Purpose, Main flow, and Important symbols.

## Decision

Validate Main flow before Purpose internally, while keeping the renderer's
existing section order. Collect call anchors only from Main flow claims that
pass all current validation. After a Purpose claim passes its existing
validation, accept it when it has no call evidence, or when at least one of its
call anchors exactly equals a validated Main flow call anchor by kind, target,
start line, and end line. A Purpose claim with call evidence and no exact match
is omitted and marks the result incomplete. If Main flow has no validated call
anchor, provider-backed Purpose claims with call evidence are omitted.

Do not rewrite or repair model evidence. If Purpose evidence is malformed or
fails any existing source, token, kind, or scope validation, report that
existing specific diagnostic before considering cross-section matching. Add a
fixed diagnostic category for a locally valid Purpose call anchor that does
not match Main flow; never include a claim, target, source excerpt, or other
provider-controlled value in that diagnostic.

For this structural rule, a Purpose claim with call evidence is treated as
provider-backed. Claims without call evidence retain the existing independent
source validation because the parser must not infer meaning from free text.
The prompt continues to instruct provider-backed Purpose claims to include and
reuse the Main flow call anchor. This relationship check guarantees anchor
identity only; it does not prove that a claim is semantically correct.

## Alternatives considered

- **Rely on prompt guidance and source validation only.** Smallest, but the
  observed response still used an unrelated provider-call target and the
  Purpose claim was dropped.
- **Infer provider-backed intent from the claim text.** Rejected because
  natural-language interpretation would be fragile and would imply a semantic
  guarantee the parser cannot provide.
- **Match typed call anchors across validated sections.** Chosen because exact
  anchor equality is deterministic, preserves source validation, and requires
  no dependency or architecture change.

## Consequences

Purpose call evidence must correspond exactly to an independently validated
Main flow call. A locally valid but unmatched call anchor causes the Purpose
claim to be omitted with a fixed reason; other validated sections remain
available. Purpose claims without call evidence are outside this relationship
check and remain subject to existing source validation. The parser still
cannot establish semantic entailment or detect a provider-backed prose claim
that supplies no call anchor.
