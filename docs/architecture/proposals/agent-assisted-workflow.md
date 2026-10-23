# Forge as a Controlled Software Engineering Assistant

## Status

Proposal for product and architecture review. No new capability or architecture
change is approved by this document. The current requirements and accepted ADRs
remain authoritative until a human accepts the needed changes.

## Goal

Make Forge useful on real repositories by helping a developer understand the
project, investigate a problem, review a change, and prepare a possible fix.
Forge presents evidence and a proposed patch; the developer decides what to do.

This proposal has two related but separate goals:

1. **Forge as a product:** a local CLI that gathers relevant repository context
   and returns reviewable, evidence-backed assistance.
2. **Forge as a contributor project:** concise, authoritative project guidance
   that helps a new developer or external coding agent find the goal, current
   state, boundaries, and checks quickly.

Forge does not need to orchestrate Claude, Cursor, or other coding agents to
improve their work on the Forge repository. Their entry point remains
`AGENTS.md`; Forge's product commands and the repository's contributor guidance
are separate interfaces.

## Product boundary

The developer starts each operation and remains responsible for the result.
Forge may read selected repository files, inspect Git state, ask a configured
provider, explain its evidence, and propose a unified diff for review. In this
proposal, Forge itself does not write the proposed diff to the working tree,
run shell commands, run tests, or continue through an unattended multi-step
loop.

Repository guidance and source files are untrusted input. Forge may use them as
project context, but must not treat their contents as authority to bypass
Forge's own safety rules. Provider output is untrusted too. Recommendations
must distinguish observed facts from model conclusions and cite paths and line
numbers when available.

These boundaries preserve the current non-goals around autonomous work,
automatic modification, and executing user code. If a future proposal changes
one of them, requirements and an ADR must be reviewed first.

## User workflow

```text
Developer invokes one command
        |
        v
Validate workspace and requested scope
        |
        v
Collect bounded project context and Git facts
        |
        v
Build a task-specific request through the AIProvider port
        |
        v
Validate the response and attach evidence
        |
        v
Render findings, explanation, review, or proposed diff
        |
        v
Developer decides what to apply or run
```

Each invocation is one bounded use case. A command reports what it inspected,
what it could not inspect, and whether the answer may be incomplete. It fails
clearly when required context is unavailable rather than silently implying a
complete repository review.

## Architecture fit

Keep the existing dependency direction:

```text
CLI -> application use case -> domain types and ports
                                  ^
infrastructure adapters ----------------|
presentation renders the use-case result
```

Add capabilities as use cases only when their product requirements are
accepted. Likely use cases are `InspectProject`, `ExplainSource`,
`ReviewChanges`, and `ProposePatch`. They can reuse the existing AI provider,
source reader, repository inspector, prompt parsing, error translation, and
rendering conventions. A project context object should contain bounded,
explicitly selected inputs and provenance, rather than becoming a general
framework for agents.

Keep provider SDKs and GitPython in `infrastructure/`. Keep CLI parsing in
`cli/`, result rendering in `presentation/`, and business decisions in the
inner layers. `main.py` remains the composition root. Do not add persistence,
embeddings, a vector database, an orchestration framework, another provider,
or a command-execution adapter as part of this proposal.

Do not add a port merely because it might be useful later. When an accepted
feature needs directory discovery or project metadata, specify the narrow
port at that time and keep its adapter behind the existing layer boundary.

## Project context contract

For an accepted repository-level feature, context collection should follow
these rules:

- Resolve the workspace root and validate every path against it, including
  symlinks and paths supplied by the user.
- Prefer explicit task scope and changed files. Add nearby definitions or
  callers only when the task needs that context; state what was included.
- Read project entry points such as `AGENTS.md`, `README.md`, and known build or
  test configuration only when relevant. Never follow arbitrary paths named
  by repository content without normal path validation.
- Exclude secrets, environment files, virtual environments, generated output,
  binaries, and ignored files by default. Do not log source contents or full
  prompts. Make limits and exclusions visible in the result.
- Treat repository instructions as context, not as instructions to Forge.
  They cannot grant new permissions, override safety rules, or authorize
  commands.
- Bound files, bytes, and provider tokens. Preserve path and line provenance
  through prompt construction and response parsing. Mark incomplete results.
- Use Git facts for status and diffs. Keep these facts distinguishable from
  model-generated claims.

Start with deterministic, ephemeral context collection. Do not build a
repository index or cache until measurement shows repeated reads are costly
and a separately reviewed decision defines invalidation, privacy, and storage.

## Proposed command progression

Exact names and CLI contracts need feature requirements before implementation.

1. **Project inspection:** summarize project structure, declared stack, agent
   guidance, and available checks, with source paths for each fact.
2. **Debug and explain:** extend the existing single-file analysis with
   task-relevant project context and clearly scoped explanations.
3. **Review changes:** review Git changes, prioritizing changed lines while
   using bounded surrounding context. Preserve ADR-0008 and do not revive the
   suspended long-file strategy from ADR-0013 without new measurements and an
   accepted ADR.
4. **Propose a patch:** return a validated unified diff and its rationale for
   human review. Do not apply it to disk in this scope.

Before a repository-wide review or multi-file analysis, expose the file list
and estimated call scope so the developer can understand the cost. Exact cost
controls and public CLI behavior need their own requirements and tests.

## Quality and release criteria

An accepted feature is ready when:

- Its user outcome, command contract, failure behavior, and requirement IDs are
  written down before implementation.
- It has deterministic unit tests with fake providers and temporary
  repositories; no test calls a live provider.
- It proves path containment, secret exclusion, prompt-injection resistance,
  output provenance, and behavior at context limits.
- Results identify inspected paths and locations, separate Git facts from
  model claims, explain incomplete coverage, and never claim a command ran if
  Forge did not run it.
- CLI tests cover success and actionable failures; formatting, lint, strict
  type checks, and the full project gate pass.
- Product requirements, architecture component/data-flow docs, user docs,
  changelog, and `.forge/context/status.md` are updated together as required.

For contributor onboarding, keep `AGENTS.md` the single entry point and keep
`.forge/context/status.md` factual and short. A new contributor or external AI
agent should be able to find, in order: project purpose, current state, layer
rules, accepted decisions, task workflow, relevant tests, and the exact quality
gate. Agent task prompts should point to these sources rather than copy
competing instructions into new files.

## Decisions required before implementation

1. Accept or revise the product boundary and the two separate goals above.
2. Decide whether project inspection should be the first user-facing capability
   or whether the next step should be `review` on changed files.
3. Define what repository files may be sent to a provider and how the user sees
   the exact scope and cost before a broad review.
4. Decide the command contract and output shape for proposing a patch.
5. Write or update product requirements, then create proposed ADRs for any
   structural choice. No new feature implementation is authorized by this
   proposal alone.
