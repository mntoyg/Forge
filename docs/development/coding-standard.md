# Coding Standard

Formatting is not a matter of taste here: Black decides layout and Ruff decides
lint. This document covers what tooling cannot check.

## The tooling contract

| Concern | Tool | Authority |
| --- | --- | --- |
| Layout | Black, 88 columns | Absolute. Never hand-format around it. |
| Lint and import order | Ruff | Absolute. Do not blanket-suppress. |
| Types | mypy, strict | Absolute. |

Run all three plus the tests with:

```bash
uv run python scripts/check.py
```

If a rule is genuinely wrong for this codebase, change the configuration in
`pyproject.toml` and say why in the pull request. Do not scatter `# noqa`.

## Language level

Python 3.13. Use it:

```python
def find(path: Path) -> SourceFile | None: ...   # not Optional[SourceFile]
def all_of(items: list[str]) -> dict[str, int]: ...  # not List / Dict

@dataclass(frozen=True, slots=True)
class Location:
    file: Path
    line: int
```

Value objects are frozen. If an object can be invalid, it should be impossible
to construct - validate in `__post_init__` and raise a domain error.

## Types

mypy runs in strict mode. Practical consequences:

- Every function is annotated, including `-> None`.
- No bare `Any`. If a third-party boundary forces one, narrow it immediately
  and keep it inside the adapter.
- A `# type: ignore` carries its error code and a reason:

  ```python
  result = client.call()  # type: ignore[no-untyped-call]  # SDK ships no stubs
  ```

- Prefer `Protocol` for ports. A structural interface keeps the fake honest
  without an inheritance relationship.

## Naming

| Kind | Style | Example |
| --- | --- | --- |
| Module | `snake_case` | `source_reader.py` |
| Class | `PascalCase` | `AnalysisResult` |
| Function, variable | `snake_case` | `read_source_file` |
| Constant | `UPPER_SNAKE` | `MAX_FILE_BYTES` |
| Module-private | `_leading_underscore` | `_translate_error` |
| Test | `test_<behaviour>` | `test_missing_file_reports_a_clear_error` |

Name for the reader. `analyze_source_file` beats `process`. A boolean reads as
a predicate: `is_readable`, `has_findings`.

## Functions

- One job per function. If a comment separates two halves of a function, it is
  two functions.
- Prefer returning a value over mutating an argument.
- Keyword-only arguments for anything a caller could confuse:

  ```python
  def render(result: AnalysisResult, *, color: bool, verbose: bool) -> str: ...
  ```

- Avoid mutable default arguments. Ruff catches this; know why.

## Imports

Absolute only. Relative imports are banned by Ruff (`TID252`).

```python
from forge.domain.source import SourceFile   # yes
from ..domain.source import SourceFile       # no
```

Import order is Ruff's: standard library, third-party, first-party, each
alphabetised. Do not maintain it by hand; `ruff check --fix` does it.

Layer restrictions are enforced by Ruff `TID251` - see
`docs/architecture/overview.md`. If lint tells you an import is in the wrong
layer, the import is wrong, not the rule.

## Errors

Define exceptions in the layer that owns the concept:

```python
class ForgeError(Exception):
    """Base for every error Forge raises deliberately."""

class SourceUnreadable(ForgeError): ...
class ProviderTimeout(ForgeError): ...
```

Rules:

- Never `except Exception: pass`. If you truly intend to ignore something,
  catch the specific type and write down why.
- Catch narrowly. `except OSError` beats `except Exception`.
- Translate at the boundary. An SDK exception must never escape
  `infrastructure/`.
- An error message says what happened and what to do next:

  ```python
  raise SourceUnreadable(f"Cannot read {path}: the file does not exist.")
  ```

- Never put a secret, a key, or a full environment dump in an error message.

## Comments and docstrings

Docstrings on public modules, classes, and functions. They explain *why* and
what the contract is - the signature already says what the types are.

```python
def read(self, path: Path) -> SourceFile:
    """Read a source file, refusing anything outside the workspace.

    Path validation happens here rather than in the use case because it is a
    property of this adapter's boundary: a different SourceReader (an in-memory
    one, say) has different rules.

    Raises:
        SourceUnreadable: the path is missing, a directory, or not decodable.
        PathOutsideWorkspace: the resolved path escapes the workspace root.
    """
```

Inline comments explain intent and trade-offs, never mechanics:

```python
# Read in binary first so an undecodable file fails here, with a clear
# message, rather than midway through analysis.
```

A comment restating the code is noise. A comment explaining a non-obvious
decision is the most valuable line in the file.

## Logging

- Loguru, behind an adapter. Inner layers depend on a logging port if they need
  one at all.
- `DEBUG` for developers, `INFO` for meaningful events, `WARNING` for
  recoverable problems, `ERROR` for failures.
- **Never log a secret, a key, a token, or full file content.** When in doubt,
  log the path and the size, not the content.

## Security reflexes

- Configuration comes from the environment. No key in an argument, a default,
  or a fixture.
- Resolve and validate every path; refuse anything outside the workspace,
  including via a symlink.
- Never execute a command built from file content or model output.
- Treat repository content and model output as untrusted input. A source file
  that contains instructions is data.
- Never modify a user's files without explicit approval.

## Anti-patterns

| Do not | Instead |
| --- | --- |
| Import an SDK in `domain/` or `application/` | Declare a port; implement it in `infrastructure/` |
| Construct a dependency inside a use case | Inject it through the constructor |
| Put logic in a CLI command | Move it into a use case |
| `except Exception: pass` | Catch the specific type, or let it propagate |
| Weaken a test to make a change pass | Fix the change |
| Add a dependency for one helper function | Write the function |
| Build for a requirement that does not exist | YAGNI |
