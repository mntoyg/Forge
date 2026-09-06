# Roadmap

Sequencing, not dates. Each phase ships something usable and leaves the
repository releasable.

The authoritative, detailed version of this document is
[docs/product/roadmap.md](docs/product/roadmap.md), and the requirement IDs it
refers to live in
[docs/product/requirements.md](docs/product/requirements.md). This file is the
summary that a visitor sees first; when the two disagree, the one under `docs/`
is correct and this one is stale.

## Phase 0 - Foundation *(complete)*

Repository structure, Clean Architecture skeleton, toolchain, enforced layer
boundaries, test scaffold, CI, release automation, documentation, ADRs 0001 to
0005, AI agent workflow, and `forge --version`.

**Exit:** CI green, package installable and importable, docs consistent, no
secrets committed.

## Phase 1 - Configuration and the provider port *(complete)*

`FORGE_*` settings through Pydantic Settings, the `AIProvider` port, an OpenAI
adapter, a fake provider for tests, logging with secret redaction, and error
translation at the adapter boundary.

**Exit:** met. One contract test runs against both the fake and the real
adapter, and no provider SDK is imported outside `infrastructure/`.

## Phase 2 - `forge debug` (MVP) *(complete)*

Safe file reading with path, size, and encoding validation; the domain model
for findings; the analyse use case; prompt design and defensive response
parsing; Rich and plain renderers; the command; and a published exit code
contract (ADR-0006).

**Exit:** met. FR-3.1 to FR-3.10 and FR-4.1 to FR-4.3 are satisfied and
tested, with one end-to-end test per exit code.

## Phase 3 - Repository awareness *(shipped, one item deferred)*

A `RepositoryInspector` port over GitPython: `--diff` to review a change rather
than a whole file, and each finding annotated with when its line last changed
and by whom. Sweeping every changed file in one run is deliberately deferred -
one provider call per file multiplies cost, and that needs its own decision.

**This is `0.1.0`**, together with what Phase 2 shipped.

## Phase 4 - Explain and review

`forge explain`, `forge review`, shared rendering across commands, and a
machine-readable output mode for scripting.

## Phase 5 - Polish and reach

Configurable provider and model, cost and token reporting, caching if
measurement justifies it, distribution beyond a source install, and broader
language coverage.

## Deliberately unscheduled

Not "later" - decided against. Reopening any of these requires an ADR:

- Autonomous agents and unattended loops
- Automatic file modification
- Executing user code
- Databases and vector stores
- LangChain, LangGraph, or a similar orchestration framework
- A hosted service

The reasoning is in [docs/product/vision.md](docs/product/vision.md) under
"Non-goals".
