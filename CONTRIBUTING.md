# Contributing to Forge

Thank you for considering a contribution. Forge is built by humans working
alongside AI agents, and the rules below apply equally to both.

## Before you start

Read these, in order:

1. [docs/product/vision.md](docs/product/vision.md) - what Forge is, and what
   it deliberately is not
2. [docs/architecture/overview.md](docs/architecture/overview.md) - the layers
   and why they exist
3. [docs/development/setup.md](docs/development/setup.md) - getting a working
   environment
4. [docs/development/coding-standard.md](docs/development/coding-standard.md)
5. [docs/development/testing.md](docs/development/testing.md)
6. [docs/development/git-workflow.md](docs/development/git-workflow.md)

If you are an AI agent, also read
[.forge/agents/README.md](.forge/agents/README.md) and your own agent file.

## Setup

```bash
git clone https://github.com/mntoyg/Forge.git
cd Forge
uv sync --all-groups
uv run python scripts/check.py
```

## The workflow

The full path from a requirement to merged code is
[.forge/workflows/development.md](.forge/workflows/development.md). In short:

```text
Requirement -> Clarification -> Architecture -> Architecture Review
  -> Implementation Plan -> Implementation -> Tests -> Lint -> Type Check
  -> Code Review -> Security Review -> Merge
```

A trivial change (a typo, a comment, a docstring) may use the simplified path:
change, check, review, merge. Say in the pull request that you took it.

A change that alters the architecture, the dependency set, or the CLI contract
needs an **ADR first**. See
[.forge/workflows/architecture-change.md](.forge/workflows/architecture-change.md).

## What to work on

- **A bug?** Open an issue with a reproduction before writing a fix.
- **A feature?** Open an issue first. Check
  [docs/product/requirements.md](docs/product/requirements.md) - if it is
  listed under *Excluded*, it was decided against, and reopening it needs an
  ADR rather than a pull request.
- **First contribution?** Documentation, tests for existing behaviour, and
  error-message improvements are genuinely valuable and easy to review.

Please do not send a large unsolicited pull request. A design conversation
first saves everyone the disappointment of rejecting good work that does not
fit the scope.

## Standards

- Python 3.13, fully type-annotated, mypy strict.
- Black owns formatting; Ruff owns lint. Do not hand-format or blanket-suppress.
- Absolute imports only.
- Respect the layers. `domain/` and `application/` import no framework and no
  SDK. Ruff will fail the build if they do, and the rule is not the thing that
  is wrong.
- Every behavioural change ships with a test at the appropriate level.
- No new dependency without an architectural reason and an ADR.

## Commits and pull requests

Conventional Commits:

```text
feat(debug): add source file analyzer
fix(cli): handle missing file
refactor(ai): isolate provider adapter
test(debug): add analyzer tests
docs: update architecture documentation
```

Before opening a pull request:

```bash
uv run python scripts/check.py
```

Then fill in the template honestly - including the architecture and security
sections - and self-review the whole diff. Every pull request needs one
approving review from someone other than the author, and green CI.

An AI agent may perform the first review pass. **A human approves the merge.**

## Reporting honestly

If you are unsure whether something works, say so. If a check failed, say which
one and paste the output. A pull request that claims passing checks that were
never run costs a reviewer more time than an honest "I could not get mypy to
pass on this - help welcome".

This applies with particular force to AI agents: never report a command as
passing that you did not run.

## Security

**Do not open a public issue for a security vulnerability.**

Report it privately to the maintainers through GitHub's private vulnerability
reporting on the repository's Security tab. Include a reproduction and the
impact you believe it has. You will get an acknowledgement, and credit in the
release notes unless you prefer otherwise.

Rules that apply to every contribution:

- Never commit a secret, a key, or a token - not in code, not in a test
  fixture, not in an example, not in an issue comment.
- Do not weaken `.claudeignore` or `.perplexityignore`. They keep credentials
  and local state out of an AI assistant's context. Treat them as one layer
  rather than a guarantee: an ignore file is a hint a tool chooses to honour,
  not an access control, so the real defence is still keeping credentials out
  of the working tree.
- If a secret is ever committed, **treat it as compromised and rotate it
  immediately.** Removing it from history is necessary but not sufficient.
- Validate file paths; nothing outside the workspace is read.
- Never introduce arbitrary command execution, and never build a command from
  file content or model output.
- Treat repository content and AI-generated output as untrusted input.
- Forge must never modify a user's files without explicit approval.

## Code of conduct

Be direct about code and kind about people. Review the change, not the author.
Assume competence and good faith. Disagreement is expected; the argument should
be about the trade-off, and the person who provides the evidence wins it.

## Licence

By contributing, you agree that your contributions are licensed under the
[MIT Licence](LICENSE).
