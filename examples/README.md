# Examples

Sample inputs used by documentation, by manual testing, and eventually by the
end-to-end tests.

Every file here is deliberately small and deliberately flawed in a known way,
so that output can be checked against a specific expectation rather than a
vague impression.

## Rules for files in this directory

- **Small.** A reader should take in the whole file at a glance.
- **Self-contained.** No imports outside the standard library.
- **Never executed.** Forge reads these; nothing runs them. They exist to be
  analysed.
- **Documented.** Each file states, in a comment at the top, what is wrong with
  it.
- **No secrets.** Not even a fake-looking one. A placeholder that resembles a
  real key trains people, and scanners, to ignore the real thing.

## Current contents

| File | Contains |
| --- | --- |
| `buggy_division.py` | An unguarded division and an off-by-one boundary |

More arrive with the features that consume them; see
`docs/product/roadmap.md`.
