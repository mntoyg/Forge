# ADR-0016 - Bind Purpose evidence to Main flow

## Status

Accepted - owner approval on 2026-11-04

## Context

FR-7 validates each explanation anchor against the submitted source snapshot.
That check does not establish that a Purpose claim points to a call also
described in Main flow. Prompt guidance alone did not prevent a
Purpose claim from using a different target or line range, which caused an
otherwise useful Purpose claim to be omitted.

The validator must make this relationship deterministic without interpreting
free-text claims or weakening the existing source, token, and AST checks. It
must also keep diagnostics free of provider-controlled text and preserve the
presentation order of Purpose, Main flow, and Important symbols.

## Decision

Validate Main flow before Purpose internally, while keeping the renderer's
existing section order. Collect call anchors only from Main flow claims that
pass all current validation. After a Purpose claim passes its existing
validation, accept it only when at least one of its call anchors exactly equals
a validated Main flow call anchor by kind, target, start line, and end line.
Every Purpose claim must therefore contain a locally valid call anchor, and a
Purpose claim without one is omitted and marks the result incomplete. If Main
flow has no validated call anchor, omit every Purpose claim that otherwise
passes its local evidence validation.

Do not rewrite or repair model evidence. If Purpose evidence is malformed or
fails any existing source, token, kind, or scope validation, report that
existing specific diagnostic before considering cross-section matching. Add a
fixed diagnostic category for a locally valid Purpose call anchor that does
not match Main flow; never include a claim, target, source excerpt, or other
provider-controlled value in that diagnostic.

Do not infer provider backing from free-text claim content. Apply the shared
call-anchor requirement to every Purpose claim so the rule remains mechanical.
The prompt instructs Purpose claims to reuse a Main flow call anchor. This
relationship check guarantees anchor identity only; it does not prove that a
claim describes the call or is otherwise semantically correct.

## Alternatives considered

- **Rely on prompt guidance and source validation only.** Smallest, but the
  observed response still used an unrelated provider-call target and the
  Purpose claim was dropped.
- **Infer which Purpose claims are provider-backed from claim text.** Rejected
  because natural-language interpretation would be fragile; applying one
  structural rule to every Purpose claim avoids that inference.
- **Match typed call anchors across validated sections.** Chosen because exact
  anchor equality is deterministic, preserves source validation, and requires
  no dependency or architecture change.

## Consequences

Every accepted Purpose claim includes a locally validated call anchor that
exactly matches an independently validated Main flow call. Missing call
evidence and valid but unmatched anchors cause Purpose to be omitted with a
fixed reason; malformed or otherwise invalid evidence keeps its existing
specific diagnostic. Other validated sections remain available. The parser
still cannot establish semantic entailment.
