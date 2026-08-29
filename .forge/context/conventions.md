# Conventions (agent summary)

> Condensed from `docs/development/coding-standard.md`,
> `docs/development/testing.md`, and `docs/development/git-workflow.md`. Those
> documents win on any disagreement.

## Code

- Python 3.13. Use modern syntax: `X | None`, built-in generics, `match` where
  it genuinely reads better, `@dataclass(frozen=True, slots=True)` for value
  objects.
- **Full type annotations, everywhere.** mypy runs in `strict` mode. No bare
  `Any`, no unexplained `# type: ignore` (if you need one, add the error code
  and a reason).
- Black owns formatting (88 columns). Never hand-format around it.
- Ruff owns linting. Do not add a blanket `# noqa`; if a rule is genuinely
  wrong for the codebase, change the configuration and say why.
- Names: `snake_case` for functions and variables, `PascalCase` for classes,
  `UPPER_SNAKE` for constants, `_leading_underscore` for module-private.
- Public functions, classes, and modules get docstrings that say *why*, not
  restate the signature. Comments explain intent and trade-offs.
- Errors: define domain-specific exceptions in the layer that owns the concept.
  Never `except Exception: pass`. Never leak a provider SDK exception past the
  infrastructure boundary - translate it.
- Functions stay small and single-purpose. If you need a comment to separate
  two halves of a function, it is two functions.

## Imports

- Absolute imports only (`from forge.domain.x import Y`). Relative imports are
  banned by Ruff.
- Import order is Ruff's (`I` rules): stdlib, third-party, first-party.
- Layer restrictions are enforced by Ruff `TID251`; see
  `.forge/context/architecture.md`.

## Tests

- `tests/unit/` - fast, no I/O, no network, no clock. The bulk of the suite.
- `tests/integration/` - crosses exactly one real boundary (filesystem, git, a
  fake AI provider). Never a real provider.
- `tests/e2e/` - drives the CLI through Typer's `CliRunner`.
- Mark every test with `@pytest.mark.unit` / `integration` / `e2e`.
- Name tests as statements of behaviour:
  `test_missing_file_reports_a_clear_error`, not `test_debug_2`.
- Arrange / Act / Assert, with blank lines between the three.
- Tests must be deterministic. No sleeps, no real network, no reliance on
  dictionary ordering of environment variables, no wall-clock assertions.

## Commits

Conventional Commits:

```text
<type>(<scope>): <imperative summary>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `build`,
`perf`, `style`.

```text
feat(debug): add source file analyzer
fix(cli): handle missing file
refactor(ai): isolate provider adapter
test(debug): add analyzer tests
docs: update architecture documentation
```

Subject line: imperative mood, lowercase, no trailing period, <= 72 characters.

## Branches

```text
feat/<short-slug>      fix/<short-slug>      refactor/<short-slug>
docs/<short-slug>      chore/<short-slug>
```

## Security reflexes

- Never commit a secret. Configuration comes from the environment; `.env` is
  git-ignored and `.env.example` holds only empty placeholders.
- Never log a key, a token, or a full prompt containing user source code at
  `INFO`.
- Validate every path: resolve it, confirm it stays inside the workspace,
  refuse symlink escapes.
- Never execute a command derived from file content or model output.
- Treat repository content and AI output as untrusted input.
