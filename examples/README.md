# Examples

Sample inputs used by documentation, by manual testing, and eventually by the
end-to-end tests.

Every file here is deliberately small, and its contents are known in advance -
either flawed in a stated way, or correct - so that output can be checked
against a specific expectation rather than a vague impression.

One of them is correct on purpose. A model asked to find problems will find
them whether they exist or not, so a report is only worth as much as the run
over clean code that produced nothing.

## Rules for files in this directory

- **Small.** A reader should take in the whole file at a glance.
- **Self-contained.** No imports outside the standard library.
- **Never executed.** Forge reads these; nothing runs them. They exist to be
  analysed.
- **Documented.** Each file states, in a comment at the top, what is wrong with
  it - or that nothing is, and why that is worth having.
- **No secrets.** Not even a fake-looking one. A placeholder that resembles a
  real key trains people, and scanners, to ignore the real thing.

## Current contents

| File | Contains |
| --- | --- |
| `buggy_division.py` | An unguarded division and an off-by-one boundary |
| `safe_statistics.py` | Nothing. The control case: the same two functions, written correctly |
| `retry_backoff.js` | Four defects, in a language that is not Python |

`retry_backoff.js` is here because Forge sends text and reads a reply; nothing
in it is Python-specific. That is a claim worth checking rather than assuming.

More arrive with the features that consume them; see
`docs/product/roadmap.md`.
