# ADR-0006 - Exit code contract

## Status

Accepted - 2026-08-30

## Context

`forge debug` is the first command, so this is the moment the CLI's exit codes
become a contract. That contract is expensive to change later: a script, a CI
step, or a git hook that branches on an exit code breaks silently when the
meaning of a number moves. Nobody notices until a pipeline reports green on a
failure.

The forces:

- **Scripting.** A CLI is a component in someone else's pipeline. `forge debug
  x.py || echo "broken"` should mean something precise.
- **Distinguishability.** "It failed" is not enough. A CI step wants to retry a
  rate limit, fail hard on a bad path, and alert on a missing key. Those are
  three different reactions to three different problems.
- **Convention.** `0` is success and `1` is generic failure on every platform
  Forge targets; `2` is conventionally a usage error. Shells reserve `126`,
  `127`, and `128+n`.
- **A trap specific to this tool.** `forge debug` finding problems in a file is
  a *successful* run. If findings produced a non-zero exit, every CI job that
  ran Forge would fail the moment the tool did its job. Linters make the
  opposite choice, and they are right to - a linter asserts a standard. Forge
  reports an opinion, and an opinion is not a gate.

`docs/architecture/components.md` carried a proposed table since Day 1. This
ADR is where it becomes binding.

## Decision

We will publish this exit code contract, and treat a change to it as breaking:

| Code | Meaning | Example |
| --- | --- | --- |
| 0 | The command did what was asked | Analysis completed - with or without findings |
| 1 | The command ran but could not produce a result | The model's reply could not be parsed |
| 2 | The input was unusable | Missing file, a directory, unreadable, too large, outside the workspace |
| 3 | Forge is not configured | No `FORGE_API_KEY`, invalid `FORGE_LOG_LEVEL` |
| 4 | The provider failed | Timeout, rate limit, rejected credentials, unreachable |

Three rules make the table hold:

1. **Findings never change the exit code.** A file with twenty problems and a
   file with none both exit `0`. A future `--fail-on-findings` flag can serve
   the gate use case explicitly, which is the honest way to offer it.
2. **Every code is reachable from exactly one class of cause**, so a caller can
   branch without parsing text.
3. **Mapping happens in `cli/` only.** The domain raises typed errors; the
   command turns them into numbers. No inner layer knows an exit code exists.

Codes 5 through 125 are reserved for future classes. Anything Forge cannot
classify exits `1`.

## Alternatives Considered

**Only 0 and 1.** Simplest, and what most small tools do. Rejected because it
forces a caller to parse stderr to decide whether to retry, and parsing a
human-readable message is exactly the coupling exit codes exist to avoid.

**Non-zero when findings exist**, the way a linter behaves. Rejected on the
argument above: it conflates "the tool worked" with "the code is good", and
would make Forge unusable in any pipeline that is not prepared to fail on an
AI's opinion. The behaviour is still available later, opt-in and named.

**A code per error subclass**, so a rate limit and a timeout differ. Rejected
as false precision: the caller's reaction to both is "wait and retry", and a
wide table invites codes that nobody handles. `4` plus a clear message carries
the same information at the level a script actually acts on.

**Use the sysexits.h conventions** (`EX_USAGE=64`, `EX_CONFIG=78`, and so on).
Rejected because they are a BSD convention that is unfamiliar to most users,
poorly supported on Windows, and would make `forge debug` return `78` where
every neighbouring tool returns a small number.

## Consequences

**Easier:**

- A script can branch on cause without reading a message.
- CI can retry `4`, fail on `2` and `3`, and treat `1` as a bug report.
- The mapping lives in one place, so a new error class has one obvious home.

**Harder:**

- The table is now a public interface. Moving a meaning between numbers is a
  breaking change requiring a major version and a superseding ADR.
- Every new error class forces a decision about which bucket it belongs to,
  and "add a new code" will usually be the wrong answer.
- Users arriving from linters will expect findings to fail the build. The
  documentation has to say plainly that it does not.

**Accepted:** the contract is documented in `README.md` and in the command's
help, and covered by end-to-end tests - one per code. An exit code without a
test is not a contract, it is an intention.
