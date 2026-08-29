"""Test doubles for the ports Forge declares.

A fake lives here rather than in each test file so that there is exactly one
definition to keep faithful to the real adapter. See
``docs/development/testing.md``.
"""

from forge.domain.ai import (
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)

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
