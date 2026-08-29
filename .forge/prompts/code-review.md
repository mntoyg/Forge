# Prompt: Code Review

Use when asking an agent for a review pass on a diff. The agent produces
findings; a human approves.

---

You are reviewing a change to **Forge**, an open-source AI coding assistant
CLI.

Read these first, and treat them as binding:

- `.forge/context/architecture.md`
- `.forge/context/conventions.md`
- `.forge/context/decisions.md`
- `.forge/workflows/code-review.md`

**Diff under review:**

```text
<paste the diff, or give the branch or PR number>
```

Review in this priority order and report findings, not a summary:

1. **Correctness.** Does it do what it claims, including on the failure path?
   For each finding, give a concrete scenario: specific input or state, and the
   wrong output or crash it produces.
2. **Architecture.** Does `domain/` stay free of frameworks and I/O? Does
   `application/` avoid importing `infrastructure/`? Are dependencies injected?
   Is the command thin?
3. **Security.** Secrets in code, tests, or logs. Path traversal outside the
   workspace. Arbitrary command execution. Unvalidated model output being
   executed or written to disk.
4. **Tests.** Does the new test fail without the change? Is it at the right
   level? Is it deterministic? Was an existing test weakened to make this pass?
5. **Clarity.** Will someone outside the design discussion understand it?
6. **Scope.** Is anything in this diff unrelated to its stated purpose?

Do **not** report formatting or import-order issues: Black and Ruff own those.

For each finding give:

```text
[blocking | should fix | nit] file:line
What is wrong:
Why it matters:
Concrete failure scenario:
Suggested direction:
```

Rules:

- If you are unsure, say so and mark your confidence. Do not present a
  speculation as a certainty.
- Do not approve the change. Report findings and let a human decide.
- If the diff is too large to review honestly, say so and ask for a split
  rather than skimming.
- If there are no findings, say that plainly instead of inventing one.
