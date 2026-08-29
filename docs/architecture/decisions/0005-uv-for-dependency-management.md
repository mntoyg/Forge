# ADR-0005 - uv for dependency management

## Status

Accepted - 2026-01-01

## Context

Forge needs a reproducible way to install dependencies, manage a virtual
environment, pin a Python version, run development tools, and build a
distribution - on Linux, macOS, and Windows, for both contributors and CI.

The forces:

- **Reproducibility.** CI and a contributor's laptop must resolve to the same
  dependency versions, or "works on my machine" becomes a standing tax.
- **Python version pinning.** ADR-0001 pins Python 3.13. The tooling should be
  able to obtain that version rather than requiring every contributor to
  install it by hand.
- **Onboarding cost.** An open-source project loses contributors at the setup
  step. Fewer commands is materially better.
- **CI speed.** The install step runs on every pull request.

## Decision

We will use **uv** for dependency management, virtual environments, Python
version management, tool execution, and building.

- `pyproject.toml` declares runtime dependencies and a `dev` dependency group.
- `uv.lock` is committed, and CI installs with `--locked` so a drift between
  the lockfile and the manifest fails the build rather than resolving silently.
- `.python-version` pins 3.13; `uv python install` obtains it.
- Development tools run through `uv run`, so everyone runs the same versions.
- `uv build` produces the distribution during the release workflow.

Setup for a new contributor is two commands, and one of them is `git clone`.

## Alternatives Considered

**pip + venv + requirements.txt.** Universally available, no extra tool to
install. Rejected because it provides no lockfile with hashes by default, no
Python version management, and no dependency groups - so reproducibility has to
be assembled from pip-tools and convention. It is more moving parts, not fewer.

**Poetry.** Mature, a real lockfile, dependency groups, widely understood.
The strongest alternative. Rejected primarily on speed - resolution and
install are substantially slower on every CI run - and because it does not
manage Python versions, so `.python-version` would still need separate
handling. Poetry also historically diverged from standard `pyproject.toml`
metadata, though this has improved.

**PDM.** Standards-compliant and capable, with a good lockfile. Rejected mainly
on adoption: a contributor is less likely to have used it, and it offers no
advantage over uv for this project.

**Hatch.** Good environment management and a natural fit with the Hatchling
build backend we already use. Rejected because its dependency locking story is
weaker than uv's, and we would still want uv-like speed.

## Consequences

**Easier:**

- One tool for environments, dependencies, Python versions, tool execution, and
  builds.
- Fast installs, which matters most in CI where it runs on every push.
- A committed lockfile makes builds reproducible and dependency changes visible
  in review.
- Contributor setup is genuinely short.

**Harder:**

- uv must be installed first; it is not in the standard toolchain. Mitigated by
  a one-line installer and a check in `scripts/setup.py` that says so clearly.
- uv is younger than pip and Poetry, and moves quickly. We accept the risk: the
  standard `pyproject.toml` metadata means migrating away would mainly mean
  regenerating a lockfile.
- Contributors used to `pip install -e .` need to learn `uv sync`. Documented
  in `docs/development/setup.md`.

**Accepted:** `uv.lock` is committed and kept current. Do not add a parallel
pip or Poetry workflow; two dependency tools in one repository guarantees they
will disagree.
