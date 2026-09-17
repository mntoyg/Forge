# Roadmap

Sequencing, not dates. Each phase ships something usable and leaves the
repository in a releasable state.

The detailed requirement IDs are in [requirements.md](requirements.md).

---

## Phase 0 - Foundation (complete)

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

## Phase 1 - Configuration and the provider port *(complete)*

**Goal:** Forge can be configured and can talk to a provider - still with no
user-facing feature.

- [x] `FORGE_*` settings via Pydantic Settings, loaded from the environment
- [x] Clear, actionable errors for missing or invalid configuration
- [x] The `AIProvider` port defined in the inner layer
- [x] An OpenAI adapter implementing it, in `infrastructure/`
- [x] A fake provider for tests
- [x] Structured logging through Loguru, behind an adapter, with secret
      redaction
- [x] Timeout and error translation at the adapter boundary

**Exit criteria:** a use case can obtain a model response through the port,
proven by tests, with no provider SDK import outside `infrastructure/`.

**Met.** `tests/integration/test_provider_contract.py` runs one contract
against both the fake and the real adapter, and includes a caller annotated
only with the port that works unchanged against either. No use case class was
created: no requirement calls for one yet, and building one to satisfy the
wording would be the speculative work ADR-0002 tells us to avoid. The first
real use case arrives with Phase 2.

---

## Phase 2 - `forge debug` (MVP) *(complete)*

**Goal:** the first capability a user would install Forge for.

- [x] Design and architecture review (ADR-0006, ADR-0007)
- [x] Safe source file reading: path validation, size limits, encoding
- [x] Domain model for a source file and a finding
- [x] The analyse use case
- [x] Prompt design and response parsing, with model output treated as
      untrusted
- [x] Rich rendering of findings, with a plain-text fallback
- [x] The `forge debug <file>` command
- [x] Distinct exit codes per failure class
- [x] End-to-end tests against a fake provider
- [x] Documentation and examples

**Exit criteria:** FR-3.1 through FR-3.10 satisfied and tested.

**Met.** Every requirement has a test, including one per exit code - ADR-0006
holds that an exit code without a test is an intention, not a contract.

**This is the first release worth tagging `0.1.0`.**

---

## Phase 3 - Repository awareness *(in progress)*

**Goal:** use git context to make answers better.

- [x] A `RepositoryInspector` port over GitPython
- [x] Debug a change rather than a file: `forge debug <file> --diff`
- [ ] Sweep every changed file in one run (`forge debug --diff` with no file).
      Deferred deliberately: one provider call per changed file multiplies
      cost, and that deserves its own decision rather than being a silent
      consequence of ADR-0008.
- [x] Blame and recent-history context for a finding (ADR-0009)
- [x] Graceful behaviour outside a git repository

---

## Phase 4 - Explain and review

**Goal:** the second and third verbs from the vision.

- [ ] `forge explain <file>` - what this code does and why
- [ ] `forge review` - review the working tree or a diff
- [ ] Shared rendering for findings across commands
- [ ] Machine-readable output for scripting (FR-4.4)

---

## Phase 5 - Polish and reach

- [ ] **Review a long file in full.** ADR-0013 chose marked windows and its own
      measurement suspended it: a 300-line marked window is not read to its end.
      Needs the smallest window that works, and a test of chunks sent alone,
      before a new decision.
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
