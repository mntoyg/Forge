# Bugfix Workflow

A bug is a difference between stated behaviour and actual behaviour. If the
behaviour was never stated, this is a feature request, not a bug - use
[feature.md](feature.md).

## 1. Reproduce before anything else

Do not start fixing until you can make it fail on demand.

```bash
# The exact command, the exact input, the exact output
forge ...
```

Record: the command, the environment (OS, Python, Forge version), the actual
output, and the expected output. If you cannot reproduce it, say so and ask
for more detail rather than guessing at a fix.

## 2. Write the failing test first

The regression test comes before the fix. It must fail for the right reason.

- Reproducible in a unit test? Put it in `tests/unit/`.
- Needs a real file or a real git repository? `tests/integration/`, using
  `tmp_path`.
- Only reproducible through the command surface? `tests/e2e/`.

Prefer the lowest level that actually reproduces the bug. A bug that only
shows up end-to-end usually means a missing seam, which is worth noting.

## 3. Find the cause, not the symptom

1. State one hypothesis.
2. Say what would disprove it.
3. Check that, with the smallest possible probe.
4. Repeat until the hypothesis survives.

Fixing the place where the wrong value became visible, rather than where it was
produced, moves the bug rather than removing it.

## 4. Fix

- The smallest change that removes the cause.
- Do not refactor surrounding code in the same commit. Note it and open a
  separate issue.
- If the fix requires an architectural change, stop and escalate - see
  [architecture-change.md](architecture-change.md).

## 5. Verify

```bash
uv run python scripts/check.py
```

- The new test passes.
- No existing test was weakened, skipped, or deleted to make it pass.
- The whole suite is green.

## 6. Commit and push

```bash
git switch main
git pull --ff-only
```

```text
fix(cli): handle missing file

Reading a path that does not exist raised an unhandled OSError and printed a
traceback. It now reports the path and exits with code 2.

Closes #42
```

The body of a bugfix commit is worth writing: what was wrong, what it does now.

## 7. Push to main

Include the before and after output. Add a `Fixed` entry to `CHANGELOG.md`
under `Unreleased`, then push the checked commit to `origin/main`.

## Severity and the simplified path

| Severity | Path |
| --- | --- |
| Crash, data loss, secret exposure | Full workflow, security review mandatory |
| Wrong output | Full workflow |
| Cosmetic (spacing, wording) | Simplified: change, check, review, commit, push |

A secret-exposure bug is never handled in a public issue thread. Report it
privately; see the security section of `CONTRIBUTING.md`.
