# Prompt: Debugging

Use when asking an agent to diagnose a failure in Forge itself.

Note: this is the prompt for debugging *the Forge codebase*. It is not the
prompt that will power the future `forge debug` command - that one will be
designed separately when the feature is scheduled.

---

You are debugging **Forge**, an open-source AI coding assistant CLI.

Read `.forge/context/architecture.md` and `.forge/workflows/bugfix.md` first.

**Reported problem:**

```text
Command:
Environment (OS, Python, Forge version):
Expected:
Actual:
Output or traceback:
```

Work in this order and show your work at each step:

## 1. Reproduce

State the exact command and input that reproduces it. If you cannot reproduce
it, stop and say what additional information you need. Do not fix a bug you
cannot see.

## 2. Localise

Name the layer the fault most likely lives in, and why:

- Wrong output for correct input -> `domain/` or `application/`
- Correct data rendered wrongly -> `presentation/`
- Failure only when touching a real file, git, or the provider ->
  `infrastructure/`
- Bad argument parsing or exit code -> `cli/`

## 3. Hypothesise

State **one** hypothesis and the evidence that would falsify it. Then run the
smallest possible check against that evidence. Repeat until a hypothesis
survives.

Do not change code while hypothesising.

## 4. Write the failing test

Before the fix, add a test that fails for the right reason, at the lowest level
that reproduces the bug.

## 5. Fix the cause

The smallest change that removes the cause, not the symptom. If the real fix
requires an architecture change, stop and escalate instead.

## 6. Verify

```bash
uv run python scripts/check.py
```

Confirm: the new test passes, no existing test was weakened or skipped, and the
whole suite is green. Report the actual output.

## Report

```text
SYMPTOM:     what the user saw
ROOT CAUSE:  the actual defect, with file and line
WHY IT HAPPENED: the reasoning error or missing case behind it
FIX:         what changed
TEST:        the regression test added
RISK:        what else this code path affects
```

If the root cause is "the design did not consider this case", say so - that is
a design finding, not just a bug.
