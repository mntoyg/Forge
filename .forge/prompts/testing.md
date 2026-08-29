# Prompt: Testing

Use when asking an agent to write or improve tests.

---

You are writing tests for **Forge**, an open-source AI coding assistant CLI.

Read these first, and treat them as binding:

- `.forge/context/conventions.md`
- `docs/development/testing.md`

**Code under test:**

```text
<paste the code, or name the module>
```

## Choose the level first

| Level | Directory | Use when | Never |
| --- | --- | --- | --- |
| Unit | `tests/unit/` | Pure logic, one unit, fakes for ports | No I/O, no network, no clock |
| Integration | `tests/integration/` | Crossing one real boundary: filesystem, git, fake provider | Never a live API |
| End-to-end | `tests/e2e/` | The command surface via Typer `CliRunner` | Never a live API |

Prefer the lowest level that actually proves the behaviour. If a behaviour can
only be tested end-to-end, say so - it usually means a seam is missing.

## What to cover

For each unit of behaviour:

1. The happy path.
2. Every distinct failure branch, with the error the user should see.
3. Boundaries: empty, missing, oversized, malformed, wrong type.
4. Any invariant the domain claims to enforce - test that it rejects the
   invalid case, not only that it accepts the valid one.

A test that only asserts "it did not raise" proves almost nothing. Assert on
the value.

## Rules

- Mark every test: `@pytest.mark.unit`, `integration`, or `e2e`.
- Name the behaviour: `test_missing_file_reports_a_clear_error`.
- Arrange / Act / Assert, separated by blank lines.
- Deterministic: no `sleep`, no real network, no wall-clock assertion, no
  dependence on environment variables the test did not set.
- **No real AI provider calls, ever.** Implement a fake of the port instead.
- Use `tmp_path` for filesystem work; never write into the repository.
- One reason to fail per test. If an assertion failing would not tell you what
  broke, split the test.
- Do not test private helpers directly; test the behaviour they support.
- Do not weaken or delete an existing test to make a new one pass.

## Deliverable

The test file, plus a short note stating:

- Which behaviours are now covered.
- Which are deliberately not covered, and why.
- Any seam that had to be added to make the code testable.
