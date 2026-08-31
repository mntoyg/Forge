"""Analysing a change rather than a whole file - ADR-0008.

The decision under test: the model sees the whole file so it can judge the
change in context, with the changed lines marked and the instructions scoped to
them. These tests assert on what is actually sent, because a prompt that
silently stops marking anything would still return plausible findings and no
test would notice.
"""

import json
from pathlib import Path

import pytest

from forge.application.analyze import AnalyzeSourceFile
from forge.application.prompt import build_request
from forge.domain.ai import CompletionResponse, Role, TokenUsage
from forge.domain.errors import NoChangesError, NotARepositoryError
from forge.domain.source import SourceFile
from tests.support.fakes import FakeProvider, FakeRepositoryInspector, FakeSourceReader

SOURCE = SourceFile(
    path=Path("app.py"),
    content="import os\n\n\ndef f(a, b):\n    return a / b\n",
)
CHANGED = frozenset({4, 5})


def _provider() -> FakeProvider:
    return FakeProvider(
        response=CompletionResponse(
            text=json.dumps({"findings": []}),
            model="fake-model",
            usage=TokenUsage(input_tokens=100, output_tokens=10),
        )
    )


# --- how the file is marked -------------------------------------------------


@pytest.mark.unit
def test_changed_lines_are_marked_and_others_are_not() -> None:
    numbered = SOURCE.numbered(CHANGED)

    lines = numbered.splitlines()
    assert lines[0] == "   1 | import os"
    assert lines[3] == "   4 > def f(a, b):"
    assert lines[4] == "   5 >     return a / b"


@pytest.mark.unit
def test_the_whole_file_is_still_shown() -> None:
    """ADR-0008: a change cannot be judged without the code around it."""
    numbered = SOURCE.numbered(CHANGED)

    assert len(numbered.splitlines()) == SOURCE.line_count
    assert "import os" in numbered


@pytest.mark.unit
def test_line_numbers_are_file_line_numbers() -> None:
    """Nothing is translated, so nothing can be translated wrongly.

    This is the argument against sending a raw diff, whose numbers live in
    hunk headers and would have to be mapped back.
    """
    numbered = SOURCE.numbered(CHANGED)

    for index, line in enumerate(numbered.splitlines(), start=1):
        assert line.startswith(f"{index:>4} ")


@pytest.mark.unit
def test_no_marking_when_no_change_is_given() -> None:
    """A whole-file run must render exactly as it did before --diff existed."""
    assert ">" not in SOURCE.numbered()
    assert SOURCE.numbered() == SOURCE.numbered(frozenset())


# --- what the prompt says ---------------------------------------------------


@pytest.mark.unit
def test_a_change_review_narrows_the_instructions() -> None:
    request = build_request(SOURCE, CHANGED)

    system = request.messages[0].content
    assert system.count("marked with >") >= 1
    assert "Do not report pre-existing problems" in system


@pytest.mark.unit
def test_a_whole_file_review_says_nothing_about_changes() -> None:
    """The added instruction must not leak into a run that has no change."""
    system = build_request(SOURCE).messages[0].content

    assert "marked with >" not in system


@pytest.mark.unit
def test_the_user_message_states_how_many_lines_changed() -> None:
    user = build_request(SOURCE, CHANGED).messages[-1].content

    assert user.startswith("File: app.py")
    assert "Changed lines: 2" in user
    assert Role.USER


# --- the use case ------------------------------------------------------------


@pytest.mark.unit
def test_a_change_review_asks_the_repository_what_changed() -> None:
    inspector = FakeRepositoryInspector(changed=CHANGED)
    provider = _provider()

    AnalyzeSourceFile(FakeSourceReader(source=SOURCE), provider, inspector)(
        Path("app.py"), changes_only=True
    )

    assert inspector.paths == [Path("app.py")]
    assert "   4 > def f(a, b):" in provider.requests[0].messages[-1].content


@pytest.mark.unit
def test_a_whole_file_review_never_touches_the_repository() -> None:
    """Someone outside version control keeps all of `forge debug` but --diff."""
    inspector = FakeRepositoryInspector()

    AnalyzeSourceFile(FakeSourceReader(source=SOURCE), _provider(), inspector)(
        Path("app.py")
    )

    assert inspector.paths == []


@pytest.mark.unit
def test_the_file_is_read_before_the_repository_is_asked() -> None:
    """A mistyped filename should say "no such file", not "no changes"."""
    from forge.domain.errors import SourceNotFoundError

    inspector = FakeRepositoryInspector()
    analyze = AnalyzeSourceFile(
        FakeSourceReader(error=SourceNotFoundError("No such file: typo.py")),
        _provider(),
        inspector,
    )

    with pytest.raises(SourceNotFoundError):
        analyze(Path("typo.py"), changes_only=True)

    assert inspector.paths == []


@pytest.mark.unit
@pytest.mark.parametrize(
    "error",
    [NotARepositoryError("not a repo"), NoChangesError("nothing changed")],
    ids=["not-a-repo", "no-changes"],
)
def test_a_repository_failure_reaches_the_caller_unchanged(error: Exception) -> None:
    provider = _provider()
    analyze = AnalyzeSourceFile(
        FakeSourceReader(source=SOURCE),
        provider,
        FakeRepositoryInspector(error=error),
    )

    with pytest.raises(type(error)):
        analyze(Path("app.py"), changes_only=True)

    assert provider.call_count == 0, "the provider must not be paid for a dead run"


@pytest.mark.unit
def test_asking_for_a_change_review_with_no_inspector_is_a_wiring_error() -> None:
    """Not a user error, so not a ForgeError - the composition root is wrong."""
    analyze = AnalyzeSourceFile(FakeSourceReader(source=SOURCE), _provider())

    with pytest.raises(RuntimeError, match="composition error"):
        analyze(Path("app.py"), changes_only=True)
