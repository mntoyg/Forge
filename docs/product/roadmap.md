# Roadmap

Sequencing, not dates. Each phase ships something usable and leaves the
repository in a releasable state.

The detailed requirement IDs are in [requirements.md](requirements.md).

---

## Phase 0 - Foundation (current)

**Goal:** a repository that humans and AI agents can work in safely.

- [x] Repository structure and Clean Architecture layer skeleton
- [x] `pyproject.toml`, uv, and the pinned toolchain
- [x] Ruff, Black, mypy strict configuration
- [x] Layer boundaries enforced mechanically (Ruff `TID251` + a runtime test)
- [x] pytest scaffold with unit / integration / e2e separation
- [x] CI: format, lint, types, tests
- [x] Release workflow triggered by a tag
- [x] Product, architecture, and development documentation
- [x] ADR-0001 through ADR-0005
- [x] AI agent roles, workflows, prompts, and shared context
- [x] Issue and pull request templates
- [x] `forge --version`

**Exit criteria:** CI green, package importable and installable, documentation
internally consistent, no secrets committed.

---

## Phase 1 - Configuration and the provider port

**Goal:** Forge can be configured and can talk to a provider - still with no
user-facing feature.

- [ ] `FORGE_*` settings via Pydantic Settings, loaded from the environment
- [ ] Clear, actionable errors for missing or invalid configuration
- [ ] The `AIProvider` port defined in the inner layer
- [ ] An OpenAI adapter implementing it, in `infrastructure/`
- [ ] A fake provider for tests
- [ ] Structured logging through Loguru, behind an adapter, with secret
      redaction
- [ ] Timeout and error translation at the adapter boundary

**Exit criteria:** a use case can obtain a model response through the port,
proven by tests, with no provider SDK import outside `infrastructure/`.

---

## Phase 2 - `forge debug` (MVP)

**Goal:** the first capability a user would install Forge for.

- [ ] Design and architecture review (this is where the work starts)
- [ ] Safe source file reading: path validation, size limits, encoding
- [ ] Domain model for a source file and a finding
- [ ] The analyse use case
- [ ] Prompt design and response parsing, with model output treated as
      untrusted
- [ ] Rich rendering of findings, with a plain-text fallback
- [ ] The `forge debug <file>` command
- [ ] Distinct exit codes per failure class
- [ ] End-to-end tests against a fake provider
- [ ] Documentation and examples

**Exit criteria:** FR-3.1 through FR-3.10 satisfied and tested.

**This is the first release worth tagging `0.1.0`.**

---

## Phase 3 - Repository awareness

**Goal:** use git context to make answers better.

- [ ] A `RepositoryInspector` port over GitPython
- [ ] Debug a change rather than a file: `forge debug --diff`
- [ ] Blame and recent-history context for a finding
- [ ] Graceful behaviour outside a git repository

---

## Phase 4 - Explain and review

**Goal:** the second and third verbs from the vision.

- [ ] `forge explain <file>` - what this code does and why
- [ ] `forge review` - review the working tree or a diff
- [ ] Shared rendering for findings across commands
- [ ] Machine-readable output for scripting (FR-4.4)

---

## Phase 5 - Polish and reach

- [ ] Configurable model and provider selection
- [ ] Cost and token reporting per invocation
- [ ] Caching of identical requests, if measurement justifies it
- [ ] Distribution beyond source install
- [ ] Broader language coverage, driven by what users actually run it on

---

## Deliberately unscheduled

These are not "later". They are excluded by decision, and reopening one needs
an ADR:

- Autonomous agents and unattended loops
- Automatic file modification
- Executing user code
- Databases and vector stores
- LangChain, LangGraph, or a similar orchestration framework
- A hosted service

## How this document changes

The roadmap is reordered by evidence, not by enthusiasm. A phase moves when a
requirement changes in [requirements.md](requirements.md); this file follows
that one.
