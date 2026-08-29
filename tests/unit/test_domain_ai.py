"""The domain's AI value objects enforce their own invariants.

Each test asserts that an *invalid* object cannot be built. Testing only that
valid input is accepted would pass just as well against a class that validates
nothing.
"""

import pytest

from forge.domain.ai import (
    MAX_TEMPERATURE,
    CompletionRequest,
    CompletionResponse,
    Message,
    Role,
    TokenUsage,
)


def _user(content: str = "Why does this fail?") -> Message:
    return Message(role=Role.USER, content=content)


@pytest.mark.unit
def test_a_message_carries_its_role_and_content() -> None:
    message = _user("explain this")

    assert message.role is Role.USER
    assert message.content == "explain this"


@pytest.mark.unit
def test_role_serialises_as_the_plain_string_providers_expect() -> None:
    assert Role.USER.value == "user"
    assert Role.SYSTEM.value == "system"
    assert Role.ASSISTANT.value == "assistant"


@pytest.mark.unit
@pytest.mark.parametrize("content", ["", "   ", "\n\t "])
def test_a_message_cannot_be_empty(content: str) -> None:
    with pytest.raises(ValueError, match="must have content"):
        Message(role=Role.USER, content=content)


@pytest.mark.unit
def test_a_message_is_immutable() -> None:
    message = _user()

    with pytest.raises(AttributeError):
        message.content = "changed"  # type: ignore[misc]


@pytest.mark.unit
def test_a_request_needs_at_least_one_message() -> None:
    with pytest.raises(ValueError, match="at least one message"):
        CompletionRequest(messages=())


@pytest.mark.unit
def test_a_request_of_only_a_system_prompt_is_rejected() -> None:
    """A system prompt sets the rules; it does not ask anything."""
    with pytest.raises(ValueError, match="at least one user message"):
        CompletionRequest(messages=(Message(role=Role.SYSTEM, content="Be terse."),))


@pytest.mark.unit
@pytest.mark.parametrize("temperature", [-0.1, MAX_TEMPERATURE + 0.1, 99.0])
def test_a_request_rejects_a_temperature_outside_the_provider_range(
    temperature: float,
) -> None:
    with pytest.raises(ValueError, match="temperature must be between"):
        CompletionRequest(messages=(_user(),), temperature=temperature)


@pytest.mark.unit
@pytest.mark.parametrize("temperature", [0.0, 1.0, MAX_TEMPERATURE])
def test_a_request_accepts_the_boundaries_of_the_temperature_range(
    temperature: float,
) -> None:
    request = CompletionRequest(messages=(_user(),), temperature=temperature)

    assert request.temperature == temperature


@pytest.mark.unit
@pytest.mark.parametrize("tokens", [0, -1])
def test_a_request_rejects_a_token_budget_that_cannot_produce_output(
    tokens: int,
) -> None:
    with pytest.raises(ValueError, match="max_output_tokens must be at least 1"):
        CompletionRequest(messages=(_user(),), max_output_tokens=tokens)


@pytest.mark.unit
def test_an_unconstrained_request_sends_no_tuning_parameters() -> None:
    """Absent means "let the provider decide", not "use a default we invented"."""
    request = CompletionRequest(messages=(_user(),))

    assert request.temperature is None
    assert request.max_output_tokens is None


@pytest.mark.unit
def test_token_usage_totals_both_directions() -> None:
    usage = TokenUsage(input_tokens=120, output_tokens=30)

    assert usage.total_tokens == 150


@pytest.mark.unit
def test_a_response_must_carry_text() -> None:
    with pytest.raises(ValueError, match="must contain text"):
        CompletionResponse(
            text="   ",
            model="m",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )


@pytest.mark.unit
def test_a_response_reports_the_model_that_actually_answered() -> None:
    """The provider may substitute a model, and the user is paying for it."""
    response = CompletionResponse(
        text="ok",
        model="gpt-4o-mini-2024-07-18",
        usage=TokenUsage(input_tokens=1, output_tokens=2),
    )

    assert response.model == "gpt-4o-mini-2024-07-18"
