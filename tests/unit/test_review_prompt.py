"""Prompt construction and byte budgets for multi-file review."""

from pathlib import Path

import pytest

from forge.application.review_prompt import (
    MAX_REVIEW_OUTPUT_TOKENS,
    MAX_REVIEW_REQUEST_BYTES,
    approximate_input_tokens,
    build_review_request,
)
from forge.domain.errors import ReviewTooLargeError
from forge.domain.review import ChangeKind, ChangeSet, ReviewFile


@pytest.mark.unit
def test_review_request_groups_files_with_real_paths_and_marked_lines() -> None:
    changes = ChangeSet(
        root=Path(),
        files=(
            ReviewFile(
                path=Path("src/app.py"),
                content="one = 1\ntwo = 2\n",
                changed_lines=frozenset({2}),
                kind=ChangeKind.MODIFIED,
            ),
            ReviewFile(
                path=Path("src/new.py"),
                content="new = True\n",
                changed_lines=frozenset({1}),
                kind=ChangeKind.RENAMED,
                previous_path=Path("src/old.py"),
            ),
        ),
        omissions=(),
    )

    request = build_review_request(changes)

    user_message = request.messages[-1].content
    assert "Path: src/app.py" in user_message
    assert "   1 | one = 1" in user_message
    assert "   2 > two = 2" in user_message
    assert "Path: src/new.py" in user_message
    assert "Renamed from: src/old.py" in user_message
    assert "untrusted DATA" in request.messages[0].content
    assert request.temperature == 0.0
    assert request.max_output_tokens == MAX_REVIEW_OUTPUT_TOKENS == 1_000


@pytest.mark.unit
def test_review_request_rejects_the_aggregate_utf8_byte_cap() -> None:
    changes = ChangeSet(
        root=Path(),
        files=(
            ReviewFile(
                path=Path("large.py"),
                content="x" * MAX_REVIEW_REQUEST_BYTES,
                changed_lines=frozenset({1}),
                kind=ChangeKind.ADDED,
            ),
        ),
        omissions=(),
    )

    with pytest.raises(ReviewTooLargeError, match="Narrow the paths"):
        build_review_request(changes)


@pytest.mark.unit
def test_token_estimate_is_rounded_up_and_labeled_as_approximate() -> None:
    request = build_review_request(
        ChangeSet(
            root=Path(),
            files=(
                ReviewFile(
                    path=Path("app.py"),
                    content="print('ok')\n",
                    changed_lines=frozenset({1}),
                    kind=ChangeKind.ADDED,
                ),
            ),
            omissions=(),
        )
    )

    byte_count = sum(
        len(message.content.encode("utf-8")) for message in request.messages
    )
    assert approximate_input_tokens(request) == (byte_count + 3) // 4
