# Forge

**An open-source, AI-first coding assistant for the terminal.**

Forge helps developers understand, debug, review, generate, and improve
software without leaving the shell.

> **Status: MVP.** `forge debug` analyzes one source file, `forge explain`
> provides an evidence-backed explanation of one selected file, and
> `forge review` reviews bounded current Git changes with one confirmed call.
> See [ROADMAP.md](ROADMAP.md) for what comes next.

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

Get a local project overview before choosing what to work on. This command
does not need an API key:

```bash
forge inspect
```

It reports guidance files, languages inferred from source-file extensions,
recognized project tooling, available check commands, and a shallow directory
outline. Each fact names the files that support it. The scan skips symlinks,
paths matched by project `.gitignore` rules, sensitive paths, virtual
environments, generated output, and known binary file types; it does not print
guidance contents, call a provider, or run commands. Any missing
evidence or scan limit is shown in the report. Git info and global exclude
rules are outside the scan.

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

To understand an unfamiliar file, use `forge explain`. The selected file is
sent to your configured provider in at most one call; Forge cites typed source
anchors and shows excerpts from that exact snapshot. Each anchor names its
kind, target, and line range. Claims with structurally invalid or mismatched
anchors are omitted and the result is marked incomplete. It does not inspect
other files, run commands, or modify files.
Structural anchor validation currently supports Python `.py` and `.pyi` files.
Other source extensions remain accepted inputs, but their evidence claims are
omitted and the result is marked incomplete.
Purpose, operation flow, and symbol responsibilities are kept distinct;
repeated summaries and name-only symbol entries are omitted. Forge asks symbol
role claims to cite where the selected file uses them, not only their import
statements. Each symbol claim names one uniquely declared class, function, or
async function; Python's AST checks that its evidence lines lie within that
declaration's scope. Ambiguous, undeclared, or out-of-scope symbols are omitted
and mark the result incomplete. These structural checks do not prove a claim is
semantically correct. Confidence is conservative: provider claims labeled
`certain` are presented as `likely`. Provider-backed purpose claims should cite
the provider call, and result-type roles should cite the return annotation or
returned value, not just an import.

```bash
forge explain src/app.py
```

Inside a repository, each finding that cites a line also says when that line
last changed and by whom, and the header says how many commits touched the file
in the last 90 days. That part comes from git rather than from the model: it
costs no tokens, and it is left out silently when there is no repository to ask
([ADR-0009](docs/architecture/decisions/0009-history-annotates-the-answer.md)).

Or review only what you changed since the last commit:

```bash
forge debug src/app.py --diff
```

To review the current worktree's staged, unstaged, and non-ignored untracked
changes together, use `forge review`. It shows the exact scope and request
estimate first and requires confirmation in an interactive terminal. Narrow
the scope by passing paths, for example `forge review src tests`. It makes at
most one provider call; deleted files and other unsupported inputs are listed
as omissions. The request is limited to 16,000 UTF-8 bytes, so larger changes
must be narrowed. The AI may miss defects; this is not a completeness check.
See the [Getting Started guide](docs/guides/getting-started.md#review-the-current-changes)
for details.

The whole file is still sent, because a change cannot be judged without the
code around it - so `--diff` narrows the answer, not the bill.

On a long file, prefer `--diff` if you are reviewing a change: marking the
changed lines keeps the model's attention on them, and it has been measured
finding a defect on the last line of a 3,807-line file that a whole-file run
misses ([ADR-0012](docs/architecture/decisions/0012-the-caveat-is-for-whole-file-runs.md)).

On a whole-file run, Forge says when the answer may only cover its start. The
model reads the beginning of a long file and stops, and "no findings" is what
that looks like from outside - so above roughly 4,000 input tokens the run
carries a caveat rather than an implication that the whole file was read
([ADR-0011](docs/architecture/decisions/0011-warn-when-a-result-may-be-partial.md)).

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
   │   OpenAI adapter, GitPython, Loguru,         │
   │       Pydantic Settings, filesystem          │
   └──────────────────────────────────────────────┘
```

The rule is enforced, not just documented: Ruff bans framework imports outside
their permitted layers, and a test parses the inner layers to assert they stay
clean. Full description in
[docs/architecture/overview.md](docs/architecture/overview.md).

## Tech stack

Python 3.13 - uv - Typer - Rich - Pydantic Settings - OpenAI SDK -
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
