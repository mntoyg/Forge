"""The OpenAI adapter, driven through a stubbed transport.

No request leaves the machine. The SDK is given an HTTP client backed by a mock
transport, so the real SDK code path runs - including its own mapping from
status code to exception - while every response is decided by the test.

The transport is built from ``httpx2`` rather than the ``httpx`` in Forge's own
dependencies: the OpenAI SDK vendors its own httpx major version, and the
client it accepts must be that one. Nothing outside this file needs to know
that, which is the adapter boundary doing its job.
"""

import json
from collections.abc import Callable
from typing import Any

import httpx2
import openai
import pytest

from forge.domain.ai import CompletionRequest, Message, Role
from forge.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from forge.infrastructure.openai_provider import OpenAIProvider

Handler = Callable[[httpx2.Request], httpx2.Response]

REQUEST = CompletionRequest(
    messages=(Message(role=Role.USER, content="Why does this fail?"),)
)


def _completion_body(
    text: str | None = "Because line 3 divides by zero.",
    *,
    choices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A minimal but well-formed chat completion payload."""
    if choices is None:
        choices = [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ]
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini-2024-07-18",
        "choices": choices,
        "usage": {"prompt_tokens": 42, "completion_tokens": 17, "total_tokens": 59},
    }


def _provider(handler: Handler) -> OpenAIProvider:
    """Build the adapter around a transport that answers via ``handler``."""
    client = openai.OpenAI(
        api_key="not-a-real-credential-for-tests",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return OpenAIProvider(api_key="unused", model="gpt-4o-mini", client=client)


def _responds(status: int, body: dict[str, Any]) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json=body)

    return handler


def _capturing(sent: dict[str, Any]) -> Handler:
    """Answer successfully, recording the request body into ``sent``."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.update(json.loads(request.read()))
        return httpx2.Response(200, json=_completion_body())

    return handler


# --- the happy path --------------------------------------------------------


@pytest.mark.integration
def test_a_successful_call_returns_a_domain_response() -> None:
    provider = _provider(_responds(200, _completion_body()))

    response = provider.complete(REQUEST)

    assert response.text == "Because line 3 divides by zero."
    assert response.usage.input_tokens == 42
    assert response.usage.output_tokens == 17
    assert response.usage.total_tokens == 59


@pytest.mark.integration
def test_the_response_reports_the_model_the_provider_actually_used() -> None:
    """The request asks for gpt-4o-mini; the provider answers with a snapshot."""
    provider = _provider(_responds(200, _completion_body()))

    assert provider.complete(REQUEST).model == "gpt-4o-mini-2024-07-18"


@pytest.mark.integration
def test_the_request_is_sent_in_the_shape_the_api_expects() -> None:
    sent: dict[str, Any] = {}

    _provider(_capturing(sent)).complete(
        CompletionRequest(
            messages=(
                Message(role=Role.SYSTEM, content="Be terse."),
                Message(role=Role.USER, content="Why does this fail?"),
            ),
            temperature=0.2,
            max_output_tokens=256,
        )
    )

    assert sent["model"] == "gpt-4o-mini"
    assert sent["messages"] == [
        {"role": "system", "content": "Be terse."},
        {"role": "user", "content": "Why does this fail?"},
    ]
    assert sent["temperature"] == 0.2
    assert sent["max_completion_tokens"] == 256


@pytest.mark.integration
def test_unset_tuning_parameters_are_omitted_rather_than_guessed() -> None:
    """Sending a default we invented would override the provider's own."""
    sent: dict[str, Any] = {}

    _provider(_capturing(sent)).complete(REQUEST)

    assert "temperature" not in sent
    assert "max_completion_tokens" not in sent


# --- error translation -----------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ProviderAuthenticationError),
        (403, ProviderAuthenticationError),
        (429, ProviderRateLimitError),
        (500, ProviderUnavailableError),
        (503, ProviderUnavailableError),
        (418, ProviderUnavailableError),
    ],
)
def test_each_failure_status_becomes_its_own_domain_error(
    status: int, expected: type[ProviderError]
) -> None:
    provider = _provider(_responds(status, {"error": {"message": "nope"}}))

    with pytest.raises(expected):
        provider.complete(REQUEST)


@pytest.mark.integration
def test_a_timeout_becomes_a_provider_timeout_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.TimeoutException("too slow", request=request)

    with pytest.raises(ProviderTimeoutError, match="FORGE_TIMEOUT_SECONDS"):
        _provider(handler).complete(REQUEST)


@pytest.mark.integration
def test_an_unreachable_provider_becomes_provider_unavailable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no route", request=request)

    with pytest.raises(ProviderUnavailableError, match="FORGE_BASE_URL"):
        _provider(handler).complete(REQUEST)


@pytest.mark.integration
def test_no_openai_exception_ever_escapes_the_adapter() -> None:
    """The whole point of ADR-0003, asserted directly.

    If this fails, a use case somewhere is about to start catching an
    OpenAI-specific type, and the port has stopped being substitutable.
    """
    provider = _provider(_responds(429, {"error": {"message": "slow down"}}))

    with pytest.raises(ProviderError) as caught:
        provider.complete(REQUEST)

    assert not isinstance(caught.value, openai.OpenAIError)
    assert type(caught.value).__module__.startswith("forge.domain")


# --- untrusted model output ------------------------------------------------


@pytest.mark.integration
def test_a_reply_with_no_choices_is_reported_not_crashed() -> None:
    provider = _provider(_responds(200, _completion_body(choices=[])))

    with pytest.raises(ProviderResponseError, match="no completion choices"):
        provider.complete(REQUEST)


@pytest.mark.integration
@pytest.mark.parametrize("content", [None, "", "   \n "])
def test_an_empty_message_is_reported_not_passed_inward(content: str | None) -> None:
    provider = _provider(_responds(200, _completion_body(content)))

    with pytest.raises(ProviderResponseError, match="empty message"):
        provider.complete(REQUEST)


@pytest.mark.integration
def test_a_reply_missing_usage_still_produces_a_response() -> None:
    """Some OpenAI-compatible servers omit usage. That is not a failure."""
    body = _completion_body()
    del body["usage"]
    provider = _provider(_responds(200, body))

    response = provider.complete(REQUEST)

    assert response.usage.input_tokens == 0
    assert response.usage.output_tokens == 0
