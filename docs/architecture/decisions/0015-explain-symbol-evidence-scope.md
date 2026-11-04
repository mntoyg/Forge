# ADR-0015 - Bind explain symbol claims to Python declaration scope

## Status

Accepted - owner approval on 2026-11-04

## Context

FR-7.4 validates typed source anchors and rejects symbol claims supported only
by imports, generic operations, assignments, or delimiters. However, a symbol
claim contains only free-text prose and anchors. The parser can verify each
anchor's source shape, but cannot tell which declared symbol the prose names
or whether that declaration owns the cited use site. A deterministic probe
accepted the same valid call anchor for both `ExplainSource` and an unrelated
symbol name. Prompt wording alone cannot close that validation gap.

The existing scope remains one selected source snapshot. Python `.py` and
`.pyi` files are the only files for which Forge validates typed anchors; other
extensions remain readable but incomplete. The new relationship check must
not claim semantic entailment, widen `AIProvider`, inspect another file, or
add a dependency.

## Decision

Add an explicit `symbol` field to each symbol claim. It must be the exact name
of one class, synchronous function, or asynchronous function declaration in
the submitted Python snapshot. Keep `claim` as a concise description of that
symbol's responsibility; never infer the subject from the prose.

For `.py` and `.pyi` snapshots, parse the same in-memory source with the
standard-library `ast` module. Accept a symbol claim only when all of the
following hold:

- The `symbol` field is a valid identifier and resolves to exactly one class,
  synchronous function, or asynchronous function declaration in the file.
- Every evidence anchor passes the existing typed-token and kind-specific
  validation, uses an allowed symbol kind (`call`, `access`, `return_type`, or
  `return_value`), and its complete line range lies within the declared
  symbol's AST source range. A class range includes its methods, allowing a
  class role to cite work performed by `__call__`.
- The claim is not rejected by the existing name-only filter.

Reject the entire symbol claim and mark the result incomplete when the subject
is missing, duplicated, unsupported, out of scope, or has invalid evidence.
If the Python AST cannot be built, omit symbol claims and state that symbol
scope validation could not be completed. Other explanation sections retain
their current typed-token validation. Non-Python files continue to omit all
evidence claims and report incomplete coverage.

This check establishes a declared subject and lexical source scope only. It
does not prove that the prose correctly describes the symbol's behavior.
Keep the one-file boundary, one-provider-call limit, read-only behavior, and
existing `AIProvider` contract.

## Alternatives Considered

- **Keep the current schema and improve the prompt.** Smallest change, but a
  fake response can still assign any symbol name to any valid anchor; rejected
  because the relationship remains unverifiable.
- **Infer the symbol name from the claim text.** Avoids a schema field, but
  natural-language parsing is ambiguous and would be a fragile heuristic;
  rejected.
- **Add a symbol subject and validate its AST scope.** Chosen because it makes
  the subject explicit and permits deterministic declaration/scope checks
  using the standard library without claiming semantic correctness.

## Consequences

Useful class and function roles can be shown only when the response identifies
their declared subject and cites validated evidence within that declaration's
scope. Duplicate names, syntax errors, and evidence outside that scope reduce
the result and visibly mark it incomplete. Variables, attributes, imported
names, and other non-class/function declarations are not symbol subjects in
this bounded version. This may omit useful symbols, but avoids presenting an
unverifiable name-to-evidence association. AST scope and typed anchors still
cannot establish semantic entailment.
