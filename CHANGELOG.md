# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

Categories: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

## [Unreleased]

### Added

- Add successful `--format text|json` output for `debug` and `inspect`; text
  remains the default.
- Add safe JSON error envelopes on stderr for Forge errors in `debug` and
  `inspect`, with empty stdout and unchanged ADR-0006 exit codes.
- Add pure presentation JSON serializers for successful debug and inspect
  results. Debug accepts typed mode, safe path, and size-warning context;
  inspect omissions now carry stable codes and optional relative paths.
- Add typed completeness metadata for debug parsing and inspect scans under
  ADR-0019.
- Draft a separate `forge explain` JSON contract; owner approval and a new ADR
  are required before implementation. FR-4.4 v1 remains debug/inspect only.
- Clarify the pending explain JSON proposal with diagnostic classifications,
  stable completeness objects, validation-availability signals, and safe paths.

### Changed

- Render the debug `--format text|json` option in command help and emit a plain,
  stable usage diagnostic when `--plain` conflicts with JSON output.
- Verify rendered debug help through the real CLI subprocess, removing ANSI
  styling before asserting visible format options across operating systems.
- Preserve the selected inspect root as a safe directory-name identifier in
  JSON and reject Windows drive-relative paths in the JSON path validator.
- Clarify JSON proposal error behavior for local `inspect` and define when
  completeness may be known from current result metadata.
- Draft a versioned machine-readable JSON output contract for deferred FR-4.4;
  owner review is required before implementation.
- Rename the distribution to `mntoyg-forge`, document tool installation, and
  publish one build to GitHub Releases and PyPI with job-scoped permissions.
- Require each `forge explain` Purpose claim to include a locally valid call
  anchor that exactly matches a validated Main flow call. Preserve existing
  specific diagnostics for invalid evidence and mark valid unmatched claims
  incomplete. This structural relationship does not prove semantic correctness.
- Give `forge explain` typed evidence anchors with exact source targets. The
  parser validates target, range, and supported source shape, drops invalid or
  mismatched claims, and marks the result incomplete. Structural token
  validation currently supports Python `.py` and `.pyi`; other source
  extensions remain accepted but their claims are omitted. This does not prove
  semantic entailment.
- Bind explain symbol claims to an explicit, unique Python class/function
  subject and require every evidence range to lie within its AST scope. Omit
  ambiguous or out-of-scope roles and mark the result incomplete; AST scope does
  not establish semantic correctness.
- Improve `forge explain` by separating purpose from operation flow, omitting
  repeated summaries and name-only symbol entries, prompting for symbol
  responsibilities as separate claims with their own usage-site evidence,
  rejecting method declarations as call evidence, and capping provider
  `certain` confidence labels at `likely`.
- Prompt provider-backed `forge explain` Purpose claims to reuse the exact
  provider-call anchor from Main flow. The parser now requires every Purpose
  claim to include a locally valid call anchor matching an independently
  validated Main flow call. Result-type roles are guided to cite the return
  annotation or returned value.
- Add safe explain analysis notes that distinguish empty or malformed sections
  from rejected claims and report specific evidence-validation reasons as fixed
  categories and counts, with one first rejection reason per claim.
- Set a shared AI usage budget of at most 14 percentage points of a weekly plan
  per local calendar day.
- Publish the `mntoyg/Forge` repository for public access; keep the archived
  repository private.

### Added

- **`forge explain <FILE>`** - explain one selected source file using at most
  one configured-provider call. Substantive claims cite validated line ranges
  and source excerpts; invalid claims are omitted and incomplete results are
  marked. Reads are bounded and the command does not modify files or run code.
- **`forge review [PATH ...]`** - preview a bounded working-tree change set and
  request confirmation before one provider call. It reports included and
  omitted paths, validates findings against changed lines, and states when
  coverage is incomplete. A non-interactive run makes no provider call.
- **`forge inspect [directory]`** - a local, deterministic overview of
  project guidance, observed languages, recognized tooling, available checks,
  and shallow structure. The report cites evidence paths and states when
  metadata is missing or a bounded scan is incomplete. It does not call a
  provider, execute commands, or modify the project.

### Documentation

- Add Proposed ADR-0017 comparing GitHub Releases only with GitHub Releases
  plus PyPI Trusted Publishing; distribution channel and package name remain
  owner decisions.
- Accept ADR-0017 option B: retain GitHub Releases and add PyPI through Trusted
  Publishing; package-name selection remains open.
- Record the approved FR-7 implementation and document the explain command.
- Add `docs/development/task.md` to record delivered capabilities and the
  staged plan for `forge explain` and subsequent features.
- Add a proposed architecture and product boundary for controlled,
  repository-aware software engineering assistance.
- Accept the bounded `forge review` MVP design in ADR-0014.

### Fixed

- Clarify API key requirements in the development setup guide and link to the
  Getting Started guide for provider configuration.

- Bound `forge review` change-set work to the accepted 16,000-byte request
  budget. Current and Git-base blob sizes are checked before source reads.
  Changed lines are mapped from the bounded source snapshot and its Git base
  blob without rereading the working tree; files that change during preparation
  are refused without truncation or a provider call.
- **The partial-result caveat no longer fires on `--diff`** (ADR-0012,
  superseding ADR-0011). Marking the changed lines carries the model's
  attention to them wherever they sit: the same defect a whole-file review
  misses at the end of a 3,807-line file is found there by `--diff`, at 44,409
  input tokens. Three general prompt variants - "read it to the last line", an
  end-of-file marker, and both - all failed to rescue the whole-file review, so
  the difference is the marking rather than the wording. Telling a user that a
  measured-reliable result may be partial teaches them to ignore the caveat
  where it matters.

## [0.1.0] - 2026-09-06

The first release worth installing. `forge debug <file>` reads a source file,
asks a configured provider about it, and reports what it finds - with a line
number where there is one, severity and confidence kept apart, and git's own
account of when each cited line last changed.

### Added

- **A caveat when a result may only cover the start of a file** (ADR-0011).
  Measured against gpt-4o-mini: one unguarded division is reported when it sits
  at 3,927 input tokens and missed at 10,225, 23,359 and 44,295 - while the
  same defect at line 6 of that 10,225-token file is found immediately. The
  model reads the beginning of a long file and stops, and "no findings" is what
  that silence looks like. Above roughly 4,000 input tokens Forge now says so,
  on stderr, after the result.
- **A spinner while the provider is thinking** (NFR-3.2). A provider call takes
  seconds, and a terminal that prints nothing for that long cannot be told from
  one that has hung. It is drawn on stderr, so a piped stdout still carries
  results only, and it is skipped entirely for `--plain` and for a pipe.
- **Line history beside each finding** - when the file is in a repository, a
  finding that cites a line now says when that line last changed and by whom,
  and the header says how many commits touched the file in the last 90 days. A
  line you have edited but not committed says so rather than naming the
  previous author.
- ADR-0009: history annotates the answer and is never put in the prompt. It
  costs no tokens, a git fact stays visibly separate from a model claim, and a
  repository that cannot answer leaves the findings untouched rather than
  failing the run.
- **`forge debug <file> --diff`** - review only the lines changed since the
  last commit. Staged and unstaged both count, and a newly created file counts
  entirely as new.
- A `RepositoryInspector` port with a GitPython adapter, so version control
  stays behind a boundary and the inner layers never learn git exists.
- ADR-0008: a change is shown as the whole file with changed lines marked,
  never as a raw diff. A model cannot judge an edit without the code around
  it, and file line numbers stay file line numbers so no location has to be
  translated back.
- **`forge debug <file>`** - the first product capability. Reads a source
  file, analyses it with the configured provider, and reports findings with
  severity, confidence, and a line number where one is identifiable.
- A published exit code contract (ADR-0006). Findings never change the exit
  code: a file with twenty problems still exits 0, because the command
  succeeded. Each of the five codes has an end-to-end test.
- `forge.domain.source` - `Severity`, `Confidence`, `Location`, `Finding`,
  `SourceFile`, `AnalysisResult`, and the `SourceReader` port. Severity and
  confidence use different vocabularies on purpose: how bad it would be and
  how sure we are are different questions.
- `FilesystemSourceReader`, refusing anything outside the workspace, over the
  size limit, not UTF-8, or empty. Symlinks are resolved before the boundary
  check, so a link inside the workspace cannot point out of it.
- Prompt-level structured output with defensive parsing (ADR-0007). A finding
  that fails validation is dropped, never repaired - a line number outside the
  file becomes no location rather than a confident wrong one.
- Rich and plain renderers, chosen automatically by whether stdout is a
  terminal, with `--plain` to force it.
- `FORGE_MAX_FILE_BYTES` to configure the size limit.
- A getting-started guide covering installation, configuration, reading the
  output, and using the exit codes from a script.
- A handover contract for AI agents. `AGENTS.md` is the single entry point;
  `CLAUDE.md`, `.cursorrules`, and `.aider.conf.yml` are thin pointers to it,
  so several tools share one set of rules instead of each carrying a copy that
  drifts.
- `.forge/context/status.md` records where the project stands, what is next,
  what is blocked, and the gotchas that would otherwise be rediscovered. It is
  the only context file that changes between sessions.
- `tests/unit/test_agent_contract.py` enforces the parts of that contract that
  erode quietly: every entry point exists and points at `AGENTS.md`, and the
  handover file stays inside a 150-line budget.
- Repository foundation: Clean Architecture layer skeleton under `src/forge/`,
  with each layer documenting its own dependency rules.
- `forge` console entry point with `--version`, and help on a bare invocation.
- Toolchain configuration in `pyproject.toml`: uv, Black, Ruff, mypy in strict
  mode, pytest with `unit` / `integration` / `e2e` markers.
- Mechanical enforcement of the dependency direction: Ruff `TID251` bans
  framework imports outside their permitted layers, and a unit test parses
  every source file under `domain/` and `application/` to assert no forbidden
  package is imported.
- Test scaffold with a fixture that strips ambient `FORGE_*` variables so tests
  cannot depend on a developer's local configuration.
- CI workflow running format, lint, type, and test checks on every pull
  request; release workflow triggered by a `v*.*.*` tag.
- Developer scripts: `scripts/setup.py`, `scripts/check.py`,
  `scripts/release.py`.
- Product documentation: vision, requirements with stable IDs, roadmap.
- Architecture documentation: overview, components, data flow.
- ADR-0001 (Python), ADR-0002 (Clean Architecture), ADR-0003 (AI provider
  abstraction), ADR-0004 (Typer), ADR-0005 (uv).
- Development documentation: setup, coding standard, testing, git workflow.
- AI agent collaboration model under `.forge/`: agent roles, the source of
  truth hierarchy, six workflows, five reusable prompts, and four shared
  context files.
- Issue templates, a pull request template, `.env.example`, and an example
  input file.
- `.gitattributes` pinning line endings to LF in the repository and the working
  tree, so a commit's line endings no longer depend on the contributor's
  `core.autocrlf` setting.
- Typed configuration in `forge.infrastructure.config`: every `FORGE_*` value
  loaded from the environment or a local `.env`, validated on load, and
  immutable once read.
- The `AIProvider` port and its value objects in `forge.domain.ai` - `Message`,
  `CompletionRequest`, `CompletionResponse`, `TokenUsage` - each validating its
  own invariants so an invalid instance cannot be constructed.
- A shared error vocabulary in `forge.domain.errors`, from `ForgeError` down to
  the five provider failures a user acts on differently.
- An OpenAI adapter in `forge.infrastructure.openai_provider` that translates
  every SDK exception into a domain error and validates the reply before
  passing it inward.
- A fake provider in `tests/support/fakes.py` that can answer *or* fail, so the
  failure branches are exercised.
- One provider contract test run against both the fake and the real adapter,
  so the fake cannot drift from what it stands in for.
- Logging through Loguru with redaction applied at the sink, so a known secret
  cannot reach the terminal regardless of what a caller logs - tracebacks and
  local variables included.

### Removed

- **`httpx` is no longer a runtime dependency** (ADR-0010). It was declared in
  Phase 1 for HTTP work that Phase 3 was expected to bring; Phase 3 brought git
  instead, and nothing has ever imported it. The `httpx2` that appears in the
  tests is the copy the OpenAI SDK vendors, and is unaffected. The import ban
  stays and now covers `httpx2` as well.

### Fixed

- **A file git ignores no longer crashes `forge debug`.** An ignored file is
  absent from git's untracked list, so the adapter treated it as tracked and
  `git blame` failed on a path git had never heard of - the GitPython
  exception escaped as a traceback, on a run whose provider call had already
  been paid for. It is now reported as "no history", which the analysis
  degrades on, and `--diff` says the file is ignored rather than claiming it
  has no changes.
- A reply Forge cannot parse now quotes what the model actually said,
  truncated and collapsed to one line. The message previously reported only
  that parsing failed, which left a user with nothing to act on and nothing to
  report - and that message is the one met on a first run against a live model.
- `FORGE_BASE_URL=` (present but blank) is now treated as unset, the same as
  the variable being absent. Following `.env.example` verbatim - copying it to
  `.env` and filling in only the key - left every other line present but
  empty, and the blank base URL reached the OpenAI SDK as an actual endpoint.
  Every request then failed with a connection error naming nothing the user
  set. This is the failure a first real run hits by following the setup guide
  exactly as written.

### Security

- `.env` is git-ignored and `.env.example` ships only empty placeholders.
- The API key is held as a `SecretStr`; tests assert it survives no `repr`,
  `str`, or `model_dump`.
- A rejected configuration value is never echoed back in the error message, so
  a key typed into the wrong variable is not printed to the terminal.
- Loguru's `diagnose` is disabled, keeping local variables - the likeliest
  place a credential is sitting when something fails - out of tracebacks.
- Every path is resolved and confirmed to stay inside the workspace before it
  is read. Forge sends what it reads to a third party, so a path that escapes
  is an exfiltration route rather than merely a crash.
- The analysis prompt states that file content is data, never instructions, so
  a comment addressed to the model is analysed rather than obeyed.
- Model output is never executed and never written to disk.
- `.claudeignore` and `.perplexityignore` keep credentials, local agent state,
  and generated files out of an AI assistant's context. The two files carry an
  identical rule set.
- Documented security principles for handling secrets, file paths, command
  execution, and untrusted repository and model content.

---

## Release history

| Version | Date | Highlights |
| --- | --- | --- |
| [0.1.0](https://github.com/mntoyg/Forge/releases/tag/v0.1.0) | 2026-09-06 | `forge debug`, `--diff`, and line history |

<!--
Template for a release section - replace X.Y.Z with the real version:

  ## [X.Y.Z] - YYYY-MM-DD

  ### Added
  ### Changed
  ### Fixed
-->
