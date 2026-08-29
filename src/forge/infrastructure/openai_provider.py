"""The OpenAI implementation of :class:`~forge.domain.ai.AIProvider`.

This module is the only place in Forge that imports the OpenAI SDK. Its job is
narrow and boring on purpose:

1. Translate a domain request into whatever the SDK wants.
2. Apply the configured timeout.
3. Translate every SDK exception into a domain error.
4. Validate the reply before letting it inward.

Step 3 is what makes the port substitutable. If an ``openai.*`` exception ever
escapes this module, some use case ends up handling an OpenAI-specific type and
the abstraction has quietly stopped working - which is why
``tests/integration/test_openai_provider.py`` asserts on it directly.
"""

from typing import assert_never

import openai
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from forge.domain.ai import (
    CompletionRequest,
    CompletionResponse,
    Message,
    Role,
    TokenUsage,
)
from forge.domain.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class OpenAIProvider:
    """Talks to an OpenAI-compatible chat completions endpoint.

    ``base_url`` makes this work against any OpenAI-compatible service,
    including a self-hosted one, without needing a second adapter.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout_seconds: float = 60.0,
        client: openai.OpenAI | None = None,
    ) -> None:
        """Build the adapter.

        Args:
            api_key: Credential for the provider.
            model: Model identifier to request.
            base_url: Endpoint override for self-hosted or proxied services.
            timeout_seconds: How long to wait for a response.
            client: A pre-built SDK client. Only tests pass this, so that a
                stubbed transport can stand in for the network. Injecting the
                SDK client rather than an HTTP client keeps this signature
                independent of whichever httpx version the SDK vendors.
        """
        self._model = model
        self._client = client or openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            # Retries are the caller's decision, not a hidden multiplier on the
            # user's bill and on the timeout they configured.
            max_retries=0,
        )

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Implement :meth:`forge.domain.ai.AIProvider.complete`."""
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[_to_message_param(m) for m in request.messages],
                temperature=(
                    openai.omit if request.temperature is None else request.temperature
                ),
                max_completion_tokens=(
                    openai.omit
                    if request.max_output_tokens is None
                    else request.max_output_tokens
                ),
            )
        except openai.APITimeoutError as error:
            raise ProviderTimeoutError(
                "The AI provider did not respond in time. Try again, or raise "
                "FORGE_TIMEOUT_SECONDS."
            ) from error
        except openai.RateLimitError as error:
            raise ProviderRateLimitError(
                "The AI provider rejected the request because of a rate or "
                "quota limit. Wait and try again, or check your plan."
            ) from error
        except (openai.AuthenticationError, openai.PermissionDeniedError) as error:
            raise ProviderAuthenticationError(
                "The AI provider rejected the credentials. Check FORGE_API_KEY."
            ) from error
        except openai.APIConnectionError as error:
            raise ProviderUnavailableError(
                "Could not reach the AI provider. Check your network connection "
                "and FORGE_BASE_URL."
            ) from error
        except openai.APIStatusError as error:
            raise ProviderUnavailableError(
                f"The AI provider returned an error (HTTP {error.status_code})."
            ) from error

        return _to_response(completion)


def _to_message_param(message: Message) -> ChatCompletionMessageParam:
    """Convert a domain message into the SDK's typed parameter.

    A dict literal built from ``message.role`` would not type-check, because
    the SDK models each role as its own TypedDict. Matching on the enum keeps
    the conversion checked, and ``assert_never`` turns adding a new role into a
    type error rather than a runtime surprise.
    """
    match message.role:
        case Role.SYSTEM:
            return ChatCompletionSystemMessageParam(
                role="system", content=message.content
            )
        case Role.USER:
            return ChatCompletionUserMessageParam(role="user", content=message.content)
        case Role.ASSISTANT:
            return ChatCompletionAssistantMessageParam(
                role="assistant", content=message.content
            )
        case _:  # pragma: no cover - unreachable while Role stays exhaustive
            assert_never(message.role)


def _to_response(completion: ChatCompletion) -> CompletionResponse:
    """Validate the reply and convert it into a domain type.

    Everything from here is untrusted input. A provider that answers with no
    choices, or with an empty message, is a normal failure to report - not an
    unhandled ``IndexError`` three layers up.
    """
    if not completion.choices:
        raise ProviderResponseError("The AI provider returned no completion choices.")

    text = completion.choices[0].message.content
    if text is None or not text.strip():
        raise ProviderResponseError("The AI provider returned an empty message.")

    usage = completion.usage
    return CompletionResponse(
        text=text,
        model=completion.model,
        usage=TokenUsage(
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        ),
    )
