# Forge

**An open-source, AI-first coding assistant for the terminal.**

Forge helps developers understand, debug, review, generate, and improve
software without leaving the shell.

> **Status: MVP.** `forge debug` works. It reads a source file, analyses it
> with an AI provider, and reports what it finds. See [ROADMAP.md](ROADMAP.md)
> for what comes next.

---

## Why Forge

A developer hitting an unfamiliar failure can read the code alone, paste it
into a browser chat window, or reach for an IDE assistant. The first is slow,
the second means copying context by hand out of the terminal, and the third
does not help in a CI log, over SSH, or in a container.

Forge fills that gap: a tool that already has the repository context, runs
where the work is happening, and returns a structured answer instead of a
conversation.

## Principles

- **Terminal-native.** Composable and scriptable, wherever a shell is.
- **Repository-aware.** It reads the actual files and history.
- **Provider-agnostic.** The AI provider sits behind a port; swapping it is a
  configuration change, not a rewrite.
- **Transparent.** It shows what it read and what it concluded.
- **Safe by default.** It never modifies your files without approval and never
  executes the code it reads.

## Install (from source)

You need [uv](https://docs.astral.sh/uv/). Python 3.13 is installed by uv, not
by you.

```bash
git clone https://github.com/mntoyg/Forge.git
cd Forge
uv sync --all-groups
uv run forge --version
```

## Usage

Set a key first - Forge uses your own:

```bash
cp .env.example .env    # then fill in FORGE_API_KEY
```

Then point it at a file:

```bash
forge debug examples/buggy_division.py
```

```text
buggy_division.py: 2 findings

  Severity   Line   Finding
  HIGH          16   Divides by len(values) without guarding an empty list
                     average([]) raises ZeroDivisionError.
                     confidence: certain
  MEDIUM        20   Off-by-one in the slice bound
                     last_n(values, 3) returns two items, not three.
                     confidence: likely

model: gpt-4o-mini-2024-07-18 | tokens: 412 in, 186 out
```

Or review only what you changed since the last commit:

```bash
forge debug src/app.py --diff
```

The whole file is still sent, because a change cannot be judged without the
code around it - so `--diff` narrows the answer, not the bill.

Forge never modifies the file and never runs it.

Output drops to plain text automatically when stdout is not a terminal, so a
pipe or a CI log stays readable. `--plain` forces it.

### Exit codes

Findings do **not** change the exit code. A file with twenty problems still
exits `0`, because the command succeeded - exit codes report whether Forge
worked, not whether your code is good. (Linters make the opposite choice; the
reasoning for ours is in [ADR-0006](docs/architecture/decisions/0006-exit-code-contract.md).)

| Code | Meaning |
| --- | --- |
| 0 | Analysis completed - with or without findings |
| 1 | Ran, but could not produce a result |
| 2 | Unusable input: missing, unreadable, too large, outside the workspace |
| 3 | Not configured |
| 4 | Provider failed: timeout, rate limit, rejected credentials |

## Architecture in one diagram

Forge follows Clean Architecture. Dependencies point inwards; infrastructure
implements the interfaces the inner layers declare.

```text
   ┌──────────────────────────────────────────────┐
   │              Presentation / CLI              │
   │        Typer commands, Rich rendering        │
   └───────────────────────┬──────────────────────┘
                           │
   ┌───────────────────────▼──────────────────────┐
   │                 Application                  │
   │       use cases, orchestration, ports        │
   └───────────────────────┬──────────────────────┘
                           │
   ┌───────────────────────▼──────────────────────┐
   │                    Domain                    │
   │   entities, value objects, rules, ports      │
   └──────────────────────────────────────────────┘
                           ▲
                           │ implements
   ┌───────────────────────┴──────────────────────┐
   │                Infrastructure                │
   │  OpenAI adapter, httpx, GitPython, Loguru,   │
   │       Pydantic Settings, filesystem          │
   └──────────────────────────────────────────────┘
```

The rule is enforced, not just documented: Ruff bans framework imports outside
their permitted layers, and a test parses the inner layers to assert they stay
clean. Full description in
[docs/architecture/overview.md](docs/architecture/overview.md).

## Tech stack

Python 3.13 - uv - Typer - Rich - Pydantic Settings - OpenAI SDK - httpx -
Loguru - GitPython - pytest - Ruff - Black - mypy

Each dependency maps to one architectural role; see
[docs/architecture/components.md](docs/architecture/components.md). Adding
another requires an ADR.

## Built with AI agents

Forge is developed by humans working with several AI agents, each with a
defined role and a shared source of truth. That collaboration model is part of
the repository, not an afterthought:

| Agent | Role |
| --- | --- |
| ChatGPT | Principal Software Architect, Prompt Engineer |
| Gemini | Principal System Architect, Distributed Systems Reviewer |
| Claude Code | Lead Implementation Engineer |
| Cursor | Software Engineer / Pair Programmer |
| Aider | Repository Coding Agent |

If you are an agent working in this repository, start at
[AGENTS.md](AGENTS.md). It is the entry point for every tool - `CLAUDE.md`,
`.cursorrules`, and `.aider.conf.yml` are thin pointers to it, so there is one
set of rules rather than one per tool.

The file that changes between sessions is
[.forge/context/status.md](.forge/context/status.md): where the project stands
today, what is next, and the gotchas worth not rediscovering.

## Documentation

| Topic | Start here |
| --- | --- |
| What Forge is and who for | [docs/product/vision.md](docs/product/vision.md) |
| What it must do | [docs/product/requirements.md](docs/product/requirements.md) |
| What is coming, in order | [ROADMAP.md](ROADMAP.md) |
| How it is built | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Why it is built that way | [docs/architecture/decisions/](docs/architecture/decisions/) |
| Using Forge | [docs/guides/getting-started.md](docs/guides/getting-started.md) |
| Setting up to develop | [docs/development/setup.md](docs/development/setup.md) |
| How to contribute | [CONTRIBUTING.md](CONTRIBUTING.md) |

## Development

```bash
uv run python scripts/check.py     # format, lint, types, tests - what CI runs
uv run pytest                      # tests only
```

## Security

Forge reads source code and talks to an AI provider, so a few rules are
absolute:

- Configuration comes from the environment. **Never commit `.env` or an API
  key.**
- Secrets never appear in logs, errors, or output.
- File paths are validated; nothing outside the workspace is read.
- Forge never executes code it reads, and never modifies files without
  approval.
- Repository content and model output are both treated as untrusted input.

To report a vulnerability, see the security section of
[CONTRIBUTING.md](CONTRIBUTING.md). Do not open a public issue.

## Licence

[MIT](LICENSE).
