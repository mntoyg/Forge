# Development Setup

## Prerequisites

- **git**
- **uv** - the only tool you need to install by hand. See
  [the uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

You do **not** need to install Python 3.13 yourself; uv will fetch it.

## Quick start

```bash
git clone https://github.com/mntoyg/Forge.git
cd Forge
uv sync --all-groups
```

That creates `.venv/`, installs Python 3.13 if needed, installs the runtime and
development dependencies, and installs Forge itself in editable mode.

Verify it:

```bash
uv run forge --version
```

Alternatively, `uv run python scripts/setup.py` does the same thing and also
creates a `.env` from `.env.example`.

## Configuration

```bash
cp .env.example .env
```

The version and help commands, along with `forge inspect`, work without an API
key. `forge debug` and `forge debug --diff` call the configured provider and
require `FORGE_API_KEY`. See the
[Getting Started guide](../guides/getting-started.md) for provider configuration
and the first analysis.

`.env` is git-ignored. **Never commit it.** Never paste a key into an issue, a
pull request, a test fixture, or a chat with an AI agent.

## Everyday commands

```bash
uv run forge --version              # run the CLI
uv run python scripts/check.py      # the full quality gate
uv run python scripts/check.py --fix  # format and autofix, then check
uv run pytest                       # tests only
uv run pytest tests/unit            # one level
uv run pytest -k "version"          # one test by name
uv run black .                      # format
uv run ruff check .                 # lint
uv run mypy                         # type check
```

`scripts/check.py` runs exactly what CI runs, in the same order. If it passes
locally, CI should agree.

## Adding a dependency

Do not add one without reading `.forge/context/decisions.md` first. If it is
justified:

```bash
uv add <package>              # runtime dependency
uv add --group dev <package>  # development dependency
```

Commit the changed `pyproject.toml` **and** `uv.lock` together. A lockfile out
of step with the manifest fails CI, which is the intended behaviour.

## Project layout

```text
.forge/     Instructions and context for AI agents
.github/    CI, release automation, templates
docs/       Product, architecture, and development documentation
src/forge/  The package, by Clean Architecture layer
tests/      unit / integration / e2e
scripts/    setup.py, check.py, release.py
examples/   Sample inputs
```

Before writing code, read `docs/architecture/overview.md`. Which layer a change
belongs to is not a matter of preference here, and Ruff will tell you if you
get it wrong.

## Editor setup

Point your editor at the project virtual environment:

```text
.venv/bin/python          # Linux, macOS
.venv\Scripts\python.exe  # Windows
```

Enable Black as the formatter, Ruff as the linter, and mypy for type checking.
There is no editor configuration committed to the repository - the tooling
configuration lives in `pyproject.toml`, so every editor and CI agree by
construction.

## Troubleshooting

**`uv: command not found`** - uv is not on PATH. Reinstall it and open a new
shell.

**`forge: command not found`** - run it through the environment:
`uv run forge --version`.

**mypy reports errors that your editor does not** - your editor is probably
using a different interpreter or a different mypy version. `uv run mypy` is the
authority.

**A test passes locally and fails in CI** - check that `uv.lock` is committed
and current. CI installs with `--locked`.

**`uv sync` fails with "network timeout"** - the default HTTP timeout is 30
seconds, which is not enough for a large wheel on a slow connection. Raise it
and retry:

```bash
UV_HTTP_TIMEOUT=900 uv sync --all-groups
```

Downloads already completed are cached, so a retry resumes rather than starting
over.

## Next

- `CONTRIBUTING.md` - how to propose a change
- `docs/development/coding-standard.md` - how the code should look
- `docs/development/testing.md` - how to test it
- `docs/development/git-workflow.md` - commits and direct pushes to `main`
