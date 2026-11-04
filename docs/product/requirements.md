# Requirements

This is the top of the source-of-truth hierarchy. When an instruction anywhere
else conflicts with this document, this document wins.

Requirement IDs are stable. `MUST`, `SHOULD`, and `MAY` follow RFC 2119.

## Status legend

| Status | Meaning |
| --- | --- |
| Done | Implemented and covered by tests |
| Planned | Agreed, scheduled, not built |
| Deferred | Agreed in principle, explicitly not now |
| Excluded | Decided against; needs an ADR to revisit |

---

## FR-1 - Foundation

| ID | Requirement | Status |
| --- | --- | --- |
| FR-1.1 | The repository MUST expose an installable Python package named `forge`. | Done |
| FR-1.2 | The package MUST provide a `forge` console entry point. | Done |
| FR-1.3 | `forge --version` MUST print the package version and exit 0. | Done |
| FR-1.4 | Invoking `forge` with no arguments MUST show help rather than fail silently. | Done |
| FR-1.5 | The source tree MUST be organised into domain, application, infrastructure, presentation, and cli layers. | Done |
| FR-1.6 | The dependency direction MUST be enforced automatically, not by convention alone. | Done |

## FR-2 - Configuration

| ID | Requirement | Status |
| --- | --- | --- |
| FR-2.1 | Configuration MUST be read from environment variables, optionally via a local `.env`. | Done |
| FR-2.2 | All configuration keys MUST be prefixed `FORGE_`. | Done |
| FR-2.3 | An API key MUST NOT be readable from a command-line argument. | Done |
| FR-2.4 | A missing or invalid configuration MUST produce a clear, actionable message - never a traceback. | Done |
| FR-2.5 | Configuration values MUST NOT be printed or logged, even at `DEBUG`. | Done |
| FR-2.6 | `.env.example` MUST document every supported key with an empty value. | Done |

## FR-3 - `forge debug` (MVP capability)

| ID | Requirement | Status |
| --- | --- | --- |
| FR-3.1 | `forge debug <file>` MUST accept a path to a single source file. | Done |
| FR-3.2 | It MUST refuse a path that does not exist, is a directory, or is not readable, with a distinct exit code. | Done |
| FR-3.3 | It MUST refuse a path that resolves outside the current workspace. | Done |
| FR-3.4 | It MUST refuse a file above a configured size limit rather than truncating silently. | Done |
| FR-3.5 | It MUST send the file content to the configured AI provider through the provider port. | Done |
| FR-3.6 | It MUST render findings in a structured, readable form, each with a location where one is identifiable. | Done |
| FR-3.7 | It MUST NOT modify the analysed file or any other file. | Done |
| FR-3.8 | It MUST NOT execute the analysed file. | Done |
| FR-3.9 | It MUST exit non-zero when analysis could not be completed. | Done |
| FR-3.10 | It MUST report provider failures (timeout, rate limit, auth) as distinct, actionable messages. | Done |
| FR-3.11 | Where version control can answer, a finding SHOULD state when its line last changed and by whom. It MUST NOT fail the run when it cannot. | Done |

## FR-4 - Output

| ID | Requirement | Status |
| --- | --- | --- |
| FR-4.1 | Human-readable output MUST be the default. | Done |
| FR-4.2 | Output MUST degrade to plain text when stdout is not a TTY. | Done |
| FR-4.3 | Errors MUST go to stderr; results MUST go to stdout. | Done |
| FR-4.4 | A machine-readable output mode SHOULD exist for scripting. | Deferred |
| FR-4.5 | Output MUST say when a result may not cover the whole file. | Done |

## FR-5 - `forge inspect` (local project overview)

Command contract: `forge inspect [directory]` defaults to `.`. Success exits
`0` and writes plain text to stdout in these sections: guidance, languages,
tooling, available checks, top-level structure, and limits or missing evidence.
Every detected language, tool, and check names its supporting path. Empty
sections say that no evidence was found. A missing directory or a non-directory
root writes an actionable error to stderr and exits `2`; unreadable candidate
files are named under limits and missing evidence, and do not abort the scan.
The scan is local, read-only, bounded to 500 filesystem entries, 200 selected
metadata files, 128,000 bytes, and three directory levels. It reads only
allowlisted metadata and ignore rules, skips symlinks, `.gitignore` matches,
known secret paths, virtual environments, and generated directories. Ignore
filtering applies project `.gitignore` files and built-in exclusions; Git
info/global excludes are not consulted. Known binary file types are excluded.
The command never prints repository file contents, invokes a provider, or
executes a reported check command. Repository guidance is identified by path
and treated as data.

| ID | Requirement | Status |
| --- | --- | --- |
| FR-5.1 | `forge inspect [directory]` MUST inspect the selected directory, defaulting to the current directory. | Done |
| FR-5.2 | Inspection MUST be deterministic and local; it MUST NOT call a provider, execute commands, or modify files. | Done |
| FR-5.3 | The overview MUST identify project guidance, declared languages and tooling, repository structure, and quality-check commands, with evidence paths. | Done |
| FR-5.4 | Claims MUST be limited to evidence found in existing readable files; missing or unreadable candidates and incomplete scans MUST be disclosed. | Done |
| FR-5.5 | Inspection MUST stay within the selected root, skip symlinks, secrets, project `.gitignore` matches, virtual environments, and generated output by default, and enforce file-count and byte limits. | Done |
| FR-5.6 | Repository content MUST be treated as untrusted data and MUST NOT override Forge safety rules. | Done |

## FR-6 - `forge review` (bounded multi-file change review)

| ID | Requirement | Status |
| --- | --- | --- |
| FR-6.1 | `forge review [PATH ...]` MUST review eligible changes in the Git worktree against `HEAD`, combining staged and unstaged tracked changes and including non-ignored untracked files; supplied paths MUST narrow the scope. | Done |
| FR-6.2 | Review MUST show the exact path scope, omissions, configured model, request byte count, approximate token count, and one-call maximum before asking for confirmation. A non-interactive invocation MUST make no provider call. | Done |
| FR-6.3 | A confirmed invocation MUST make at most one provider call, using full current file contents with real line numbers and changed lines marked. It MUST NOT truncate or split requests; the combined UTF-8 byte length of completion message contents MUST be at most 16,000 bytes, and output MUST be capped at 1,000 tokens. | Done |
| FR-6.4 | Review MUST abort before provider submission for a known sensitive path or supported inline-secret pattern, and MUST NOT print or log secret values. Secret detection is heuristic and MUST NOT be described as exhaustive. | Done |
| FR-6.5 | Review MUST disclose deletions, binary files, symlinks, and ignored untracked files as omissions; tracked files remain eligible despite ignore rules. A Git-detected rename MUST be identified and reviewed at its current destination. | Done |
| FR-6.6 | Every accepted finding MUST cite a submitted repository-relative path and one-based changed line from the planned current snapshot. Invalid model paths or locations MUST be discarded and the response marked incomplete. Evidence excerpts MUST come from that snapshot. | Done |
| FR-6.7 | Review MUST be read-only, MUST NOT run project commands or checks, and MUST NOT continue an autonomous loop. Repository content and provider output MUST be treated as untrusted data. | Done |

## FR-7 - `forge explain` (single-file explanation)

Approved contract: [explain-command.md](../architecture/proposals/explain-command.md).

| ID | Requirement | Status |
| --- | --- | --- |
| FR-7.1 | `forge explain <FILE>` MUST explain only the explicitly selected source file; it MUST NOT scan adjacent files, Git history, or run project commands. | Done |
| FR-7.2 | The command MUST read through `SourceReader`, require a regular, non-empty UTF-8 file inside the workspace, enforce `FORGE_MAX_FILE_BYTES` (default 200,000 bytes), and refuse rather than truncate over-limit input. The actual read MUST remain bounded if a file grows after its size check. | Done |
| FR-7.3 | An invocation MUST make at most one call to the configured `AIProvider`. Help and user documentation MUST disclose that the selected source is sent to that provider. Source and full prompts MUST NOT be logged. | Done |
| FR-7.4 | Each substantive explanation claim MUST cite one or more typed evidence anchors in the submitted snapshot. An anchor MUST include a supported kind (`call`, `access`, `return_type`, `return_value`, or `operation`), an exact source target, and an inclusive one-based line range. For `.py` and `.pyi` files, validate ranges, exact target tokens, and kind-specific shape against that snapshot; comments and strings MUST NOT satisfy anchors. Each symbol claim MUST identify its subject using the exact name of one uniquely declared class, function, or async function. Its call/access/return-type/return-value evidence ranges MUST lie within that declaration's AST scope. Missing, duplicate, unsupported, out-of-scope, or invalid symbol claims MUST be omitted and mark results incomplete. Other extensions remain valid inputs but their claims are not accepted as evidence-validated and the result MUST be marked incomplete. Structural checks do not prove semantic entailment. State uncertainty and missing context. | Done |
| FR-7.5 | The command MUST be read-only, MUST NOT execute source or repository commands, discover adjacent files, retry with more context, or start an autonomous loop. Source and provider output MUST be treated as untrusted data. | Done |
| FR-7.6 | Every Purpose claim MUST include at least one `call` evidence anchor that passes existing source validation and exactly equals by kind, target, start line, and end line a call anchor in a Main flow claim that independently passed validation. Main flow MUST be validated before Purpose internally, without changing render order. If no such anchor matches, omit the Purpose claim and mark the result incomplete. Missing, malformed, or otherwise invalid Purpose evidence MUST retain its existing specific diagnostic. | Done |

## NFR-1 - Quality

| ID | Requirement | Status |
| --- | --- | --- |
| NFR-1.1 | All code MUST be fully type-annotated and pass mypy in strict mode. | Done |
| NFR-1.2 | All code MUST pass Ruff and Black checks. | Done |
| NFR-1.3 | The test suite MUST be deterministic. | Done |
| NFR-1.4 | Unit tests MUST NOT require an API key or network access. | Done |
| NFR-1.5 | CI MUST run format, lint, type, and test checks on every pull request. | Done |
| NFR-1.6 | Every user-facing behaviour MUST have a test. | Done |

## NFR-2 - Security

| ID | Requirement | Status |
| --- | --- | --- |
| NFR-2.1 | Secrets MUST NOT be committed to the repository. | Done |
| NFR-2.2 | Secrets MUST NOT appear in logs, errors, or terminal output. | Done |
| NFR-2.3 | Every file path MUST be validated against escape outside the workspace. | Done |
| NFR-2.4 | Forge MUST NOT execute arbitrary commands derived from file content or model output. | Done |
| NFR-2.5 | Forge MUST NOT modify user files without explicit approval. | Done |
| NFR-2.6 | Repository content and model output MUST be treated as untrusted input. | Done |

## NFR-3 - Usability

| ID | Requirement | Status |
| --- | --- | --- |
| NFR-3.1 | Every error message MUST state what went wrong and what to do next. | Done |
| NFR-3.2 | A long-running operation SHOULD show progress. | Done |
| NFR-3.3 | The tool MUST run on Linux, macOS, and Windows. | Done |

## NFR-4 - Portability and cost

| ID | Requirement | Status |
| --- | --- | --- |
| NFR-4.1 | The AI provider MUST be replaceable without changing domain or application code. | Done |
| NFR-4.2 | The model MUST be configurable. | Done |
| NFR-4.3 | Forge SHOULD avoid sending more content than the task requires. | Done |

## Excluded

These are decided against. Reopening one requires an ADR.

| ID | Excluded | Reason |
| --- | --- | --- |
| EX-1 | Autonomous multi-step agents | Out of product scope; see [vision.md](vision.md) |
| EX-2 | Automatic file modification | Safety; the human applies changes |
| EX-3 | Executing user code | Safety |
| EX-4 | Databases and vector stores | Unnecessary complexity at this scope |
| EX-5 | LangChain / LangGraph or similar frameworks | The provider port is sufficient and keeps the dependency surface small |
| EX-6 | A hosted service | Forge is a local CLI using the user's own key |

## Traceability

Every pull request that changes behaviour references the requirement ID it
satisfies. A change that satisfies no requirement is either scope creep or a
missing requirement - resolve which before merging.
