"""The AI provider port and the value objects that cross it.

This is the seam ADR-0003 exists to create. The inner layers know only what is
in this module; the OpenAI SDK, HTTP, retries, and JSON shapes all live behind
it in :mod:`forge.infrastructure`.

Nothing here imports a framework or performs I/O, so every type in this module
can be constructed and asserted on in a unit test with no setup.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

MAX_TEMPERATURE = 2.0


class Role(StrEnum):
    """Who a message came from.

    A :class:`~enum.StrEnum` rather than a bare string so that an invalid role
    cannot reach an adapter, while the value still serialises as the plain
    string every provider expects.
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class Message:
    """One turn of a conversation.

    Raises:
        ValueError: the content is empty or whitespace only.
    """

    role: Role
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("A message must have content.")


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    """What Forge asks a provider for.

    The request carries no provider-specific field. Anything an individual
    provider needs beyond this - headers, response formats, tool schemas - is
    the adapter's business, not the caller's.

    Raises:
        ValueError: the request could never produce a useful answer.
    """

    messages: tuple[Message, ...]
    temperature: float | None = None
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("A completion request needs at least one message.")
        if not any(message.role is Role.USER for message in self.messages):
            raise ValueError(
                "A completion request needs at least one user message; "
                "a system prompt alone has nothing to answer."
            )
        if (
            self.temperature is not None
            and not 0.0 <= self.temperature <= MAX_TEMPERATURE
        ):
            raise ValueError(
                f"temperature must be between 0.0 and {MAX_TEMPERATURE}, "
                f"got {self.temperature}."
            )
        if self.max_output_tokens is not None and self.max_output_tokens < 1:
            raise ValueError(
                f"max_output_tokens must be at least 1, got {self.max_output_tokens}."
            )


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """What a request cost, in tokens.

    Token spend is the user's money, so it is part of the response rather than
    something buried in an adapter's log line.
    """

    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class CompletionResponse:
    """What a provider gave back, once it has been validated.

    Reaching this type means the response was well-formed. Whether the *text*
    is correct is a separate question, and not one the provider can answer.

    Raises:
        ValueError: the response carries no text.
    """

    text: str
    model: str
    usage: TokenUsage

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("A completion response must contain text.")


class AIProvider(Protocol):
    """The port every AI provider adapter implements.

    Deliberately narrow. Widening it toward whatever one SDK happens to expose
    is how this abstraction stops being useful - see ADR-0003.

    A :class:`~typing.Protocol` rather than an abstract base class, so a test
    fake satisfies it structurally without inheriting from anything.
    """

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send ``request`` to the provider and return its validated answer.

        Every implementation must fail with a
        :class:`forge.domain.errors.ProviderError` subclass and never with a
        transport or SDK exception - that translation is what makes the port
        substitutable.

        Raises:
            ProviderTimeoutError: the provider did not answer in time.
            ProviderRateLimitError: a rate or quota limit was hit.
            ProviderAuthenticationError: the credentials were rejected.
            ProviderUnavailableError: the provider could not be reached.
            ProviderResponseError: the reply could not be used.
        """
        ...
