# ADR-0010 - Remove httpx as a declared dependency

## Status

Accepted - 2026-09-01

## Context

`httpx` has been in `project.dependencies` since Phase 1, described as
"infrastructure: HTTP transport". It was declared before any HTTP existed, on
a prediction. `docs/architecture/components.md` recorded the prediction
plainly: it is "the approved transport for the HTTP work Phase 3 brings, and
removing it now only to re-add it later would cost an ADR each way".

Phase 3 has now arrived. It brought GitPython, not HTTP. The prediction did not
hold, and nothing in the roadmap between here and `1.0` obviously restores it.

Three facts settle the rest:

- **Nothing imports it.** The only httpx in this repository is `httpx2` - the
  copy the OpenAI SDK (v3) vendors under its own name - which appears in two
  integration tests.
- **It could not be used with the provider adapter anyway.** `httpx` and
  `httpx2` are different packages and do not interchange: a client handed to
  the SDK must be an `httpx2` client. Whatever the declared httpx is for, it is
  not the one thing Forge currently talks to over HTTP.
- **`0.1.0` changes who pays for the drift.** Until now this was a line in a
  file. At a release it becomes a package every installation downloads, resolves
  against, and never loads.

Removing a runtime dependency requires an ADR, per
`.forge/context/decisions.md`. So does keeping one whose stated reason has
expired. This record exists because the drift itself was the thing that could
not continue.

## Decision

We will **remove `httpx` from `project.dependencies`** and re-lock.

The Ruff import ban stays, and **gains `httpx2` beside it**. The ban list
exists to stop an inner layer importing an infrastructure package, and `httpx2`
is the one actually present in the environment - so it is the one an inner
layer could actually import by accident. `tests/unit/test_package.py` mirrors
the list, as its own comment requires.

When Forge needs HTTP of its own - a provider with no SDK, a webhook, a
registry lookup - it returns in the same change as the code that calls it, with
an ADR that can name the caller instead of predicting one.

## Alternatives Considered

**Keep it, and write down why.** The honest version of the status quo: state in
an ADR that HTTP is expected and that the dependency is held for it. Rejected
because a dependency justified by a prediction that has already failed once is
not justified, it is deferred - and the cost of deferring it moves onto users
at `0.1.0`. Two ADRs later it would still not be imported.

**Keep it and start using it:** pass an explicit client to the OpenAI SDK to
control timeouts and proxies. This is the argument that would have saved it,
and it fails on a fact rather than on judgement: the SDK takes an `httpx2`
client. Doing this needs `httpx2`, which arrives with the SDK. The declared
`httpx` is not what would be used.

**Remove it and drop the import ban with it.** Tidier - the ban would name a
package that is no longer installed. Rejected because the ban costs nothing,
and packages arrive transitively without anyone deciding to add them. The day
httpx reappears under some other dependency, it is already guarded.

## Consequences

**Easier:**

- One fewer package resolved and downloaded per installation, and one fewer
  thing in the lock file's dependency graph to audit.
- The dependency list describes what the code does. Every remaining entry maps
  to an import that exists, which is the property that makes the list worth
  reading at all.
- The boundary gets stronger rather than weaker: the banned list now names the
  httpx that is actually importable here.

**Harder:**

- The first HTTP that Forge does itself needs an ADR and a lock update before
  it can be written. That is the intended cost, and it is small next to a
  dependency nobody can account for.
- The `httpx` / `httpx2` confusion does not disappear - it is the SDK's, not
  ours. The note explaining it moves from "the dependency we hold" to "the
  thing that surprises you in the tests", and stays in
  `.forge/context/status.md` where a new agent will meet it.

**Accepted:** if HTTP arrives next month, this is one ADR and one line of
`pyproject.toml` to undo. That is the whole cost of being wrong here, and it is
smaller than the cost of shipping a dependency nobody can explain.
