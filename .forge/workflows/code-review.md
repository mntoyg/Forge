# Code Review Workflow

Every change is reviewed by someone other than its author. An AI agent may
perform the first pass; a human performs the last one.

## What a review is for

In priority order:

1. **Correctness** - does it do the right thing, including on the failure path?
2. **Architecture** - does it respect the layers and the dependency direction?
3. **Security** - can it leak a secret, escape the workspace, or execute
   something it should not?
4. **Tests** - do they actually prove the behaviour, or only exercise it?
5. **Clarity** - will this be readable by someone who was not in the design
   discussion?
6. **Scope** - is anything here that does not belong to this change?

Style is not on the list. Black and Ruff decide style; a review comment about
formatting means the tooling is misconfigured.

## Reviewer checklist

### Correctness

- [ ] The change does what the PR says it does.
- [ ] Failure paths are handled, not swallowed. No bare `except Exception`.
- [ ] Boundaries are considered: empty input, missing file, huge file, no
      network, no configuration.
- [ ] No behaviour changed that the PR did not mention.

### Architecture

- [ ] `domain/` imports no framework and no SDK, and performs no I/O.
- [ ] `application/` depends only on `domain/` and on ports.
- [ ] External systems are reached only through an adapter in
      `infrastructure/`.
- [ ] Dependencies are injected, not constructed inside a use case.
- [ ] The command in `cli/` is thin: parse, call one use case, render, map the
      exit code.
- [ ] No new dependency, or one with an accepted ADR.

### Security

- [ ] No secret, key, token, or credential in code, tests, fixtures, or logs.
- [ ] File paths are resolved and confirmed to stay inside the workspace.
- [ ] No arbitrary command execution, and no shelling out to a
      content-derived string.
- [ ] Model output is validated before use, never executed, never written to a
      file without approval.
- [ ] Error messages do not echo secrets or full environment contents.

### Tests

- [ ] New behaviour has a test, and the test fails without the change.
- [ ] The test sits at the right level.
- [ ] No real network call, no real provider call, no sleep, no clock
      dependency.
- [ ] Test names state behaviour.

### Documentation

- [ ] Docs contradicted by this change are updated in the same PR.
- [ ] `CHANGELOG.md` has an entry, if the change is user-visible.

## How to write a review comment

- Say what is wrong and why it matters. "This reads the whole file into memory;
  a 200 MB file will exhaust the process" beats "inefficient".
- Distinguish **blocking**, **should fix**, and **nit**. Label them.
- Suggest a direction, not a rewrite.
- Ask a question when you are unsure rather than asserting.
- Approve when it is good enough to merge, not when it is what you would have
  written.

## For an AI agent reviewing

- Read the whole diff, not the summary of it.
- Do not approve. An agent produces findings; a human approves.
- Rank findings and state your confidence. A speculative finding presented as
  a certainty wastes the author's time.
- Do not report style issues that the formatter already owns.
- If the diff is too large to review honestly, say so and ask for it to be
  split.

## Author responsibilities

- Self-review the diff before requesting review.
- Explain the *why* in the PR description; the *what* is in the diff.
- Respond to every comment - fixed, or a reason it stays.
- Do not force-push over a review in progress; add commits and squash on merge.
