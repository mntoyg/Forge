# Prompt: Implementation

Use when handing an approved design to an implementing agent - normally Claude
Code, sometimes Cursor or Aider for narrower work.

---

You are implementing an approved design for **Forge**, an open-source AI
coding assistant CLI.

Read these first, and treat them as binding:

- `.forge/context/project.md`
- `.forge/context/architecture.md`
- `.forge/context/conventions.md`
- `.forge/context/decisions.md`
- `.forge/agents/claude.md` (or your own agent file)

**Design to implement:**

```text
<paste the approved design, or link the issue and ADR>
```

**Scope:**

```text
IN:  <what to build>
OUT: <what not to touch>
```

## Before you write code

State your plan first, and wait if anything is ambiguous:

1. The files you will create or modify, in the order you will do it.
2. The layer each one belongs to.
3. The tests you will add, and at which level.
4. Anything in the design that is unclear or appears to conflict with an ADR.

Do not begin until the plan is stated. If the design requires a new
dependency, a new external service, or a change to the layer boundaries -
**stop and escalate**; that needs an ADR first.

## While implementing

- Build inward-out: domain, then port, then use case, then adapter, then
  renderer, then command.
- Full type annotations; mypy runs strict.
- No framework or SDK import in `domain/` or `application/`.
- Dependencies are injected, never constructed inside a use case.
- Handle the failure path, do not swallow it.
- Validate every file path; refuse anything resolving outside the workspace.
- No secret in code, tests, fixtures, or log output.
- Keep the diff to the stated scope.

## Tests

- A unit test for every domain rule, including the invalid case.
- A unit test for every use case branch, using a fake port.
- An integration test for every adapter, against a temporary directory or a
  fake provider - never a live API.
- An e2e test for the command: one success, one likely user error.
- Deterministic: no network, no sleep, no wall-clock assertion.

## When you are done

Run the real gate and report the real output:

```bash
uv run python scripts/check.py
```

Then report in this format:

```text
DONE:      what was actually completed
NOT DONE:  what was in scope but is not finished, and why
DECISIONS: choices a reviewer should check
RISKS:     what might be wrong
CHECKS:    the exact commands run and their real results
NEXT:      the recommended next step
```

Never report a check as passing if you did not run it.
