# Testing

## The strategy

```text
        e2e            few, slow, high confidence
         ^
    integration        some, medium
         ^
       unit            many, fast, the bulk of the suite
```

Test at the **lowest level that actually proves the behaviour**. A behaviour
that can only be proven end-to-end usually means a seam is missing - that is a
design finding worth reporting, not something to work around.

## The three levels

### Unit - `tests/unit/`

The majority of the suite. A unit test exercises one piece of logic in
isolation, with fakes for any port.

- No filesystem, no network, no subprocess, no clock, no randomness.
- Runs in milliseconds.
- Covers domain rules and use case branches.

```python
@pytest.mark.unit
def test_analysis_rejects_an_empty_source_file() -> None:
    with pytest.raises(InvalidSourceFile):
        SourceFile(path=Path("a.py"), content="")
```

### Integration - `tests/integration/`

Crosses exactly **one** real boundary: the filesystem, a real git repository
created in `tmp_path`, or a stubbed HTTP transport.

- **Never a live AI provider.** Not once, not behind a marker, not "only when a
  key is present".
- Use `tmp_path`; never write inside the repository.

```python
@pytest.mark.integration
def test_reader_refuses_a_path_outside_the_workspace(tmp_path: Path) -> None:
    ...
```

### End-to-end - `tests/e2e/`

Drives the CLI the way a user would, through Typer's `CliRunner`. In-process:
no subprocess, no installed binary needed.

```python
@pytest.mark.e2e
def test_version_flag_reports_the_package_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout
```

One success path and the most likely user error per command is usually enough.
Exhaustive branch coverage belongs at the unit level, where it is cheap.

## Determinism is a hard requirement

The suite must produce the same result on every machine, on every run, forever.

Banned outright:

- Real AI provider calls
- Real network access of any kind
- `time.sleep`
- Assertions on the current time
- Dependence on ambient environment variables (`conftest.py` strips `FORGE_*`
  for exactly this reason)
- Dependence on filesystem state outside `tmp_path`

A flaky test is worse than no test: it trains everyone to ignore a red build.
Fix it or delete it, and say which.

## Faking the provider

This is the payoff of ADR-0003. A use case takes an `AIProvider`, so a test
supplies one:

```python
class FakeProvider:
    """Returns a canned response, or raises, on demand."""

    def __init__(self, response: AnalysisResponse | None = None,
                 error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    def complete(self, request: AnalysisRequest) -> AnalysisResponse:
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response
```

The fake must be able to **fail**. A fake that only ever succeeds produces a
suite that never exercises the timeout, rate-limit, or auth-failure paths -
which are precisely the paths users will hit.

## What to cover

For every unit of behaviour:

1. The happy path.
2. Every distinct failure branch, and the message the user should see.
3. Boundaries: empty, missing, oversized, malformed, wrong type.
4. Every invariant the domain claims. Test that the invalid case is *rejected*,
   not only that the valid one is accepted.

## Writing a good test

- **Name the behaviour.** `test_missing_file_reports_a_clear_error`, not
  `test_read_2`.
- **Arrange, Act, Assert**, separated by blank lines.
- **One reason to fail.** If a failing assertion would not tell you what broke,
  split the test.
- **Assert on the value**, not merely that nothing raised.
- **Test behaviour, not implementation.** A test that breaks on a rename of a
  private helper is testing the wrong thing.
- **Mark it**: `@pytest.mark.unit`, `integration`, or `e2e`. `--strict-markers`
  means an unregistered marker fails the run.

## Running

```bash
uv run pytest                  # everything
uv run pytest tests/unit       # one level
uv run pytest -m unit          # by marker
uv run pytest -k "version"     # by name
uv run pytest -x               # stop at the first failure
uv run pytest -vv              # verbose
```

## Coverage

There is no coverage gate, deliberately. A percentage target produces tests
written to move a number rather than to catch a defect.

The real bar is in review: **does every behaviour this change introduces have a
test that would fail without the change?** If not, it is not done.

## Rules that are not negotiable

1. Never call a real AI provider.
2. Never commit a real API key, in a fixture or anywhere else.
3. Never weaken, skip, or delete a test to make a change pass. If a test is
   genuinely wrong, fix it in its own commit and say why.
4. A bug fix ships with a regression test that fails before the fix.
