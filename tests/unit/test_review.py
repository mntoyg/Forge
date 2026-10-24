"""Planning is local; a confirmed review makes one call through the fake port."""

import json
from pathlib import Path

import pytest

from forge.application.review import ReviewChanges, ReviewPlan
from forge.domain.ai import CompletionResponse, TokenUsage
from forge.domain.errors import (
    NoChangesError,
    ReviewTooLargeError,
    SensitiveContentError,
)
from forge.domain.review import (
    ChangeKind,
    ChangeOmission,
    ChangeSet,
    OmissionReason,
    ReviewFile,
)
from tests.support.fakes import FakeProvider


class FakeChangeSetReader:
    """Record requested paths while returning a stable local snapshot."""

    def __init__(self, changes: ChangeSet) -> None:
        self.changes = changes
        self.paths: list[tuple[Path, ...]] = []

    def read(self, paths: tuple[Path, ...] = ()) -> ChangeSet:
        self.paths.append(paths)
        return self.changes


def _changes(
    *,
    path: Path = Path("src/app.py"),
    content: str = "one = 1\ntwo = 0\n",
    omissions: tuple[ChangeOmission, ...] = (),
) -> ChangeSet:
    return ChangeSet(
        root=Path(),
        files=(
            ReviewFile(
                path=path,
                content=content,
                changed_lines=frozenset({2}),
                kind=ChangeKind.MODIFIED,
            ),
        ),
        omissions=omissions,
    )


def _provider(text: str | None = None) -> FakeProvider:
    return FakeProvider(
        response=CompletionResponse(
            text=text
            or json.dumps(
                {
                    "findings": [
                        {
                            "path": "src/app.py",
                            "line": 2,
                            "summary": "Division by zero",
                            "detail": "The divisor can be zero.",
                            "severity": "high",
                            "confidence": "certain",
                        }
                    ]
                }
            ),
            model="fake-returned-model",
            usage=TokenUsage(input_tokens=321, output_tokens=45),
        )
    )


@pytest.mark.unit
def test_prepare_builds_a_preview_without_calling_the_provider() -> None:
    reader = FakeChangeSetReader(_changes())
    provider = _provider()
    review = ReviewChanges(reader, provider, model="configured-model")

    plan = review.prepare((Path("src"),))

    assert reader.paths == [(Path("src"),)]
    assert isinstance(plan, ReviewPlan)
    assert plan.model == "configured-model"
    assert plan.request is not None
    assert plan.request_bytes == sum(
        len(message.content.encode("utf-8")) for message in plan.request.messages
    )
    assert plan.approximate_tokens == (plan.request_bytes + 3) // 4
    assert provider.call_count == 0


@pytest.mark.unit
def test_complete_makes_one_call_and_returns_actual_usage_and_snapshot_evidence() -> (
    None
):
    provider = _provider()
    review = ReviewChanges(
        FakeChangeSetReader(_changes()), provider, model="configured"
    )
    plan = review.prepare()

    result = review.complete(plan)

    assert provider.call_count == 1
    assert result.model == "fake-returned-model"
    assert result.usage == TokenUsage(input_tokens=321, output_tokens=45)
    assert result.incomplete is False
    assert result.findings[0].evidence == "two = 0"


@pytest.mark.unit
def test_known_omissions_make_a_provider_result_incomplete() -> None:
    omission = ChangeOmission(Path("deleted.py"), OmissionReason.DELETED)
    provider = _provider()
    review = ReviewChanges(
        FakeChangeSetReader(_changes(omissions=(omission,))),
        provider,
        model="configured",
    )

    result = review.complete(review.prepare())

    assert result.incomplete is True
    assert result.omissions == (omission,)


@pytest.mark.unit
def test_discarded_model_findings_make_a_provider_result_incomplete() -> None:
    provider = _provider(
        json.dumps(
            {
                "findings": [
                    {
                        "path": "src/app.py",
                        "line": 1,
                        "summary": "Unchanged-line claim",
                        "detail": "The location is outside the changed lines.",
                    }
                ]
            }
        )
    )
    review = ReviewChanges(
        FakeChangeSetReader(_changes()), provider, model="configured"
    )

    result = review.complete(review.prepare())

    assert result.findings == ()
    assert result.incomplete is True


@pytest.mark.unit
@pytest.mark.parametrize(
    ("path", "content"),
    [
        (Path(".env.local"), "FORGE_API_KEY = 'not-a-real-key-value-12345'\n"),
        (Path("src/app.py"), "token = 'not-a-real-key-value-12345'\n"),
        (Path("src/private_key.pem"), "ordinary contents\n"),
    ],
)
def test_sensitive_scope_aborts_before_provider_without_echoing_values(
    path: Path, content: str
) -> None:
    provider = _provider()
    review = ReviewChanges(
        FakeChangeSetReader(_changes(path=path, content=content)),
        provider,
        model="configured",
    )

    with pytest.raises(SensitiveContentError) as caught:
        review.prepare()

    assert "not-a-real-key-value-12345" not in str(caught.value)
    assert provider.call_count == 0


@pytest.mark.unit
def test_rename_from_a_sensitive_path_is_refused() -> None:
    source = ReviewFile(
        path=Path("src/app.py"),
        previous_path=Path(".env"),
        content="ordinary = 'text'\n",
        changed_lines=frozenset({1}),
        kind=ChangeKind.RENAMED,
    )
    changes = ChangeSet(root=Path(), files=(source,), omissions=())
    provider = _provider()

    with pytest.raises(SensitiveContentError):
        ReviewChanges(
            FakeChangeSetReader(changes), provider, model="configured"
        ).prepare()

    assert provider.call_count == 0


@pytest.mark.unit
def test_over_limit_plan_aborts_before_provider() -> None:
    provider = _provider()
    review = ReviewChanges(
        FakeChangeSetReader(_changes(content="x" * 16_000)),
        provider,
        model="configured",
    )

    with pytest.raises(ReviewTooLargeError):
        review.prepare()

    assert provider.call_count == 0


@pytest.mark.unit
def test_an_omissions_only_plan_cannot_call_the_provider() -> None:
    omission = ChangeOmission(Path("removed.py"), OmissionReason.DELETED)
    changes = ChangeSet(root=Path(), files=(), omissions=(omission,))
    provider = _provider()
    review = ReviewChanges(FakeChangeSetReader(changes), provider, model="configured")

    plan = review.prepare()

    assert plan.request is None
    with pytest.raises(NoChangesError):
        review.complete(plan)
    assert provider.call_count == 0
