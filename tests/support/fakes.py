"""Test doubles for the ports Forge declares.

A fake lives here rather than in each test file so that there is exactly one
definition to keep faithful to the real adapter. See
``docs/development/testing.md``.
"""

import json
from pathlib import Path

from forge.domain.ai import (
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)
from forge.domain.source import SourceFile

DEFAULT_RESPONSE = CompletionResponse(
    text="A canned answer.",
    model="fake-model",
    usage=TokenUsage(input_tokens=10, output_tokens=5),
)


class FakeProvider:
    """An :class:`~forge.domain.ai.AIProvider` that answers from memory.

    It can also **fail**, which is the point. A fake that only ever succeeds
    produces a suite that never exercises the timeout, rate-limit, or
    auth-failure branches - precisely the ones users hit.

    Every request is recorded, so a test can assert on what a use case actually
    sent rather than only on what came back.
    """

    def __init__(
        self,
        *,
        response: CompletionResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        if response is not None and error is not None:
            raise ValueError("A FakeProvider either answers or fails, not both.")
        self._response = response if response is not None else DEFAULT_RESPONSE
        self._error = error
        self.requests: list[CompletionRequest] = []

    @property
    def call_count(self) -> int:
        return len(self.requests)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Implement :meth:`forge.domain.ai.AIProvider.complete`."""
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return self._response


class FakeSourceReader:
    """A :class:`~forge.domain.source.SourceReader` backed by memory.

    Like :class:`FakeProvider`, it must be able to fail: every refusal the real
    reader makes - missing, unreadable, too large, outside the workspace - is a
    path a user will hit, and a use case test that cannot reach them is not
    testing the use case.
    """

    def __init__(
        self,
        *,
        source: SourceFile | None = None,
        error: Exception | None = None,
    ) -> None:
        if source is not None and error is not None:
            raise ValueError("A FakeSourceReader either reads or fails, not both.")
        self._source = source
        self._error = error
        self.paths: list[Path] = []

    def read(self, path: Path) -> SourceFile:
        """Implement :meth:`forge.domain.source.SourceReader.read`."""
        self.paths.append(path)
        if self._error is not None:
            raise self._error
        if self._source is not None:
            return self._source
        return SourceFile(path=path, content="x = 1\n")


class FakeRepositoryInspector:
    """A :class:`~forge.domain.source.RepositoryInspector` backed by memory.

    Like the other fakes it must be able to fail: not being in a repository,
    and having nothing to review, are both normal answers a user will meet.
    """

    def __init__(
        self,
        *,
        changed: frozenset[int] | None = None,
        error: Exception | None = None,
    ) -> None:
        if changed is not None and error is not None:
            raise ValueError(
                "A FakeRepositoryInspector either answers or fails, not both."
            )
        self._changed = changed if changed is not None else frozenset({2})
        self._error = error
        self.paths: list[Path] = []

    def changed_lines(self, path: Path) -> frozenset[int]:
        """Implement RepositoryInspector.changed_lines."""
        self.paths.append(path)
        if self._error is not None:
            raise self._error
        return self._changed


def findings_json(*findings: object, key: str = "findings") -> str:
    """Build a model reply containing ``findings``.

    Tests that care about *parsing* should hand-write their JSON, malformed
    edges included. This helper is for tests that care about something else and
    just need a well-formed reply.
    """
    return json.dumps({key: list(findings)})
