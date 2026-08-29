# Feature Workflow

For a new user-visible capability. Follow
[development.md](development.md) in full; this file adds the feature-specific
detail.

## 1. Frame it as a user outcome

Write the outcome before the design:

```text
As a developer, I want to <do something>, so that <benefit>.
```

Then write the command shape, because in a CLI the command *is* the contract:

```bash
forge <command> [ARGS] [--options]
```

Decide up front:

- What is printed on success?
- What is printed on each failure, and what is the exit code?
- What happens when the input is missing, empty, huge, or not text?
- Does this need network access? If so, what happens offline?

## 2. Design

Answer these before any code exists:

| Question | Where the answer lives |
| --- | --- |
| What new domain concepts appear? | `domain/` |
| What use case orchestrates it? | `application/` |
| What external systems are touched? | a port + an adapter in `infrastructure/` |
| How is the result rendered? | `presentation/` |
| What is the command surface? | `cli/` |

If the feature needs a new dependency or a new external service, stop: that is
an [architecture change](architecture-change.md) and needs an ADR.

## 3. Plan

Write the file list and the order. A good plan for a Forge feature usually
looks like:

1. Domain types and rules (+ unit tests)
2. Port definition
3. Use case (+ unit tests using a fake port)
4. Adapter (+ integration test against the real boundary, not the real API)
5. Renderer (+ unit test on formatting)
6. Command (+ e2e test through `CliRunner`)
7. Docs and `CHANGELOG.md`

Build inward-out: domain first, command last. The command should be the
smallest file in the change.

## 4. Branch and commit

```bash
git switch -c feat/<short-slug>
```

Commit in the order above, one logical step per commit:

```text
feat(debug): add source file value objects
test(debug): cover source file validation
feat(debug): add analyze use case
```

## 5. Tests

- Every new domain rule: a unit test, including the invalid case.
- Every use case: a unit test with a fake port, covering success and each
  failure branch.
- Every adapter: an integration test against a temporary directory, a
  temporary git repository, or a fake provider - never a live API.
- The command: one e2e test for success, one for the most likely user error.

## 6. Documentation

A feature is not done until:

- `docs/product/requirements.md` reflects it, if it changes scope.
- `docs/architecture/components.md` lists any new component.
- `docs/architecture/data-flow.md` shows the new path, if it adds one.
- `README.md` shows the command, if it is user-facing.
- `CHANGELOG.md` has an `Added` entry under `Unreleased`.
- `examples/` has a sample input, if the feature reads files.

## 7. Pull request

Fill in the template honestly, including the architecture and security
sections. Request review. Do not merge your own PR without a second reader.
