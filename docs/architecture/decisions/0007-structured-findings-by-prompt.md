# ADR-0007 - Structured findings by prompt, not by constrained decoding

## Status

Accepted - 2026-08-30

## Context

FR-3.6 requires `forge debug` to render findings "in a structured, readable
form, each with a location where one is identifiable". A finding therefore
needs fields - a description, a severity, a line number - not a paragraph of
prose. Something has to turn a language model's output into those fields.

Modern providers offer a direct answer: constrained decoding, where a JSON
schema is passed with the request and the server guarantees conforming output
(`response_format` on OpenAI). It is reliable, and it removes a class of
parsing failure entirely.

Three forces pull the other way:

- **ADR-0003 keeps the port narrow.** `AIProvider.complete` takes messages and
  returns text. Adding a schema parameter widens it toward one provider's
  feature set, which is the failure mode that ADR warns about by name.
- **`FORGE_BASE_URL` promises OpenAI-compatible endpoints work.** Many
  self-hosted and proxy servers implement `/chat/completions` but not schema-
  constrained decoding, or implement it partially. A hard dependency on the
  feature quietly breaks the self-hosting story the vision commits to.
- **Defensive parsing is required either way.** Model output is untrusted
  input by project rule. Even with a guaranteed schema, a line number can
  point past the end of the file, a severity can be a word we do not know, and
  a description can be empty. Constrained decoding removes *syntactic* failure,
  not *semantic* failure, so the validation layer has to exist regardless.

The third point is decisive. Constrained decoding does not remove work; it
makes one already-necessary layer succeed more often.

## Decision

We will ask for JSON **in the prompt**, and parse it defensively in the
application layer.

- The prompt states the exact shape required and gives one worked example.
- The adapter returns text, unchanged. `AIProvider` is not widened.
- A parser in `application/` extracts the JSON, validates every field against
  the domain rules, and discards a finding it cannot trust rather than
  inventing a value for it.
- Output that yields no usable finding at all raises
  `ProviderResponseError`, which the CLI maps to exit code `1` per ADR-0006.
- A line number outside the file's range is dropped to "no location" rather
  than reported wrongly. A confident wrong location is worse than none: it
  sends the reader to the wrong place and costs their trust in every other
  finding.

Constrained decoding stays available as a **later, adapter-level
optimisation**: an adapter may use it internally to make its own text more
reliable, provided the port signature does not change and behaviour is
identical when the endpoint does not support it. That needs its own ADR.

## Alternatives Considered

**Constrained decoding via `response_format`.** Reliable, and the obvious
modern answer. Rejected for now on the three forces above - chiefly that it
either widens the port or hides a provider capability behind it, and that it
breaks against OpenAI-compatible servers that do not implement it. It is the
first thing to revisit if prompt-level JSON proves unreliable in practice, and
the parser stays useful either way.

**Free-form prose, rendered as-is.** No parsing, no failure mode, and the
model's full nuance survives. Rejected because it does not satisfy FR-3.6:
there is no location to attach, nothing to sort by severity, and no path to
the machine-readable output mode in FR-4.4.

**A strict line-oriented format** (`SEVERITY|LINE|MESSAGE`). Easier to parse
than JSON and degrades more gracefully. Rejected because models follow JSON
instructions markedly better than invented formats, and because a message
containing the delimiter breaks it - which is exactly the input we should
expect from a tool that reads source code.

**Tool/function calling** to receive structured arguments. Same objection as
constrained decoding, plus a larger surface: it would put tool schemas in the
port, which is a much bigger widening than one format flag.

## Consequences

**Easier:**

- `AIProvider` stays exactly as narrow as ADR-0003 intends.
- Any OpenAI-compatible endpoint works, including self-hosted ones.
- Parsing and validation are pure functions in `application/`, unit-testable
  against recorded strings with no provider involved - including the malformed
  cases, which are the ones worth testing.
- Swapping to constrained decoding later changes an adapter, not a contract.

**Harder:**

- The model can return unparseable output, and sometimes will. That is a real
  failure path a user will meet, so it gets a clear message and its own exit
  code rather than a traceback.
- The prompt is now load-bearing. A careless edit to it can break parsing
  without breaking a single unit test, so prompt changes are reviewed as code
  and covered by tests over recorded outputs.
- Two things now define the finding shape - the prompt and the domain model -
  and they can drift. They are kept in the same review.

**Accepted:** the parser treats every field as hostile, and a finding that
fails validation is dropped rather than repaired. Silently repairing model
output would make Forge confidently wrong, which is the one failure this tool
cannot afford.
