"""Prepare and execute one confirmed, bounded repository change review."""

from dataclasses import dataclass
from pathlib import Path

from forge.application.parsing import parse_review_findings
from forge.application.review_prompt import (
    approximate_input_tokens,
    build_review_request,
)
from forge.application.review_security import contains_inline_secret, sensitive_path
from forge.domain.ai import AIProvider, CompletionRequest
from forge.domain.errors import NoChangesError, SensitiveContentError
from forge.domain.review import ChangeSet, ChangeSetReader, ReviewResult


@dataclass(frozen=True, slots=True)
class ReviewPlan:
    """A complete local plan that can be shown before any provider call."""

    changes: ChangeSet
    request: CompletionRequest | None
    model: str
    request_bytes: int
    approximate_tokens: int


class ReviewChanges:
    """Separate review planning from the single provider call for consent."""

    def __init__(
        self, change_sets: ChangeSetReader, provider: AIProvider, *, model: str
    ) -> None:
        self._change_sets = change_sets
        self._provider = provider
        self._model = model

    def prepare(self, paths: tuple[Path, ...] = ()) -> ReviewPlan:
        """Collect and validate the exact snapshot without contacting a provider."""
        changes = self._change_sets.read(paths)
        for source in changes.files:
            if (
                sensitive_path(source.path)
                or (
                    source.previous_path is not None
                    and sensitive_path(source.previous_path)
                )
                or contains_inline_secret(source.content)
            ):
                raise SensitiveContentError(
                    "Review stopped because a sensitive path or recognized "
                    f"inline-secret pattern was detected in {source.path.as_posix()}. "
                    "Remove it from scope."
                )

        if not changes.files:
            return ReviewPlan(
                changes=changes,
                request=None,
                model=self._model,
                request_bytes=0,
                approximate_tokens=0,
            )

        request = build_review_request(changes)
        request_bytes = sum(
            len(message.content.encode("utf-8")) for message in request.messages
        )
        return ReviewPlan(
            changes=changes,
            request=request,
            model=self._model,
            request_bytes=request_bytes,
            approximate_tokens=approximate_input_tokens(request),
        )

    def complete(self, plan: ReviewPlan) -> ReviewResult:
        """Make at most one provider call for a plan the CLI has confirmed."""
        if plan.request is None:
            raise NoChangesError(
                "No current text files are available to review; inspect the omissions."
            )
        response = self._provider.complete(plan.request)
        parsed = parse_review_findings(response.text, plan.changes)
        return ReviewResult(
            findings=parsed.findings,
            omissions=plan.changes.omissions,
            model=response.model,
            usage=response.usage,
            incomplete=bool(plan.changes.omissions) or not parsed.complete,
        )
