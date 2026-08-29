"""One contract, checked against every implementation of the provider port.

``docs/development/testing.md`` says the fake must stay faithful, because a
fake that drifts from the real adapter produces a suite that passes while the
product is broken. This file is how that promise is kept: each test runs
against both the fake and the real OpenAI adapter behind a stubbed transport.

Add an implementation of :class:`~forge.domain.ai.AIProvider` and it belongs in
``PROVIDERS`` here, not in a test file of its own.
"""

from collections.abc import Callable
from typing import Any

import httpx2
import openai
import pytest

from forge.domain.ai import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    Message,
    Role,
    TokenUsage,
)
from forge.domain.errors import ProviderError, ProviderRateLimitError
from forge.infrastructure.openai_provider import OpenAIProvider
from tests.support.fakes import FakeProvider

REQUEST = CompletionRequest(
    messages=(Message(role=Role.USER, content="Why does this fail?"),)
)

ANSWER = "Because line 3 divides by zero."

_BODY: dict[str, Any] = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "created": 0,
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": ANSWER},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 42, "completion_tokens": 17, "total_tokens": 59},
}


def _openai(status: int, body: dict[str, Any]) -> OpenAIProvider:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json=body)

    return OpenAIProvider(
        api_key="unused",
        model="gpt-4o-mini",
        client=openai.OpenAI(
            api_key="not-a-real-credential-for-tests",
            max_retries=0,
            http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        ),
    )


def _succeeding_fake() -> AIProvider:
    return FakeProvider(
        response=CompletionResponse(
            text=ANSWER,
            model="gpt-4o-mini",
            usage=TokenUsage(input_tokens=42, output_tokens=17),
        )
    )


def _succeeding_openai() -> AIProvider:
    return _openai(200, _BODY)


def _failing_fake() -> AIProvider:
    return FakeProvider(error=ProviderRateLimitError("slow down"))


def _failing_openai() -> AIProvider:
    return _openai(429, {"error": {"message": "slow down"}})


SUCCEEDING: list[Callable[[], AIProvider]] = [_succeeding_fake, _succeeding_openai]
FAILING: list[Callable[[], AIProvider]] = [_failing_fake, _failing_openai]
IDS = ["fake", "openai"]


@pytest.mark.integration
@pytest.mark.parametrize("build", SUCCEEDING, ids=IDS)
def test_a_provider_returns_a_validated_domain_response(
    build: Callable[[], AIProvider],
) -> None:
    response = build().complete(REQUEST)

    assert isinstance(response, CompletionResponse)
    assert response.text == ANSWER
    assert response.usage.total_tokens == 59


@pytest.mark.integration
@pytest.mark.parametrize("build", FAILING, ids=IDS)
def test_a_provider_fails_only_with_a_domain_error(
    build: Callable[[], AIProvider],
) -> None:
    """Substitutability lives or dies here.

    A caller written against the port catches ``ProviderError``. If one
    implementation raised something else, that caller would work in tests and
    crash in production - or the reverse.
    """
    with pytest.raises(ProviderError) as caught:
        build().complete(REQUEST)

    assert type(caught.value).__module__.startswith("forge.domain")


@pytest.mark.integration
@pytest.mark.parametrize("build", FAILING, ids=IDS)
def test_a_rate_limit_is_the_same_class_from_every_implementation(
    build: Callable[[], AIProvider],
) -> None:
    with pytest.raises(ProviderRateLimitError):
        build().complete(REQUEST)


@pytest.mark.integration
def test_a_caller_written_against_the_port_needs_no_provider_knowledge() -> None:
    """Phase 1's exit criterion, expressed as the code it enables.

    ``ask`` is annotated with the port, not with a concrete class. It
    type-checks and runs unchanged against both implementations, which is what
    "the provider is replaceable without changing inner code" means in
    practice. It lives in the test rather than in ``application/`` because no
    requirement calls for a use case yet - see YAGNI in ADR-0002.
    """

    def ask(provider: AIProvider, question: str) -> str:
        request = CompletionRequest(
            messages=(Message(role=Role.USER, content=question),)
        )
        return provider.complete(request).text

    assert ask(_succeeding_fake(), "Why does this fail?") == ANSWER
    assert ask(_succeeding_openai(), "Why does this fail?") == ANSWER


@pytest.mark.integration
def test_the_fake_records_what_a_caller_actually_sent() -> None:
    """Asserting on the request is how a use case's prompt gets tested."""
    fake = FakeProvider()

    fake.complete(REQUEST)
    fake.complete(REQUEST)

    assert fake.call_count == 2
    assert fake.requests[0].messages[0].content == "Why does this fail?"


@pytest.mark.integration
def test_a_fake_cannot_be_configured_to_both_answer_and_fail() -> None:
    """An ambiguous double would make its tests mean nothing."""
    with pytest.raises(ValueError, match="either answers or fails"):
        FakeProvider(
            response=CompletionResponse(
                text="x", model="m", usage=TokenUsage(input_tokens=1, output_tokens=1)
            ),
            error=ProviderRateLimitError("slow down"),
        )
