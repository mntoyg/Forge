# ADR-0003 - AI provider abstraction

## Status

Accepted - 2026-01-01

## Context

Forge's core capability depends on an AI provider. That dependency is the most
volatile thing in the system:

- Models are deprecated on the provider's schedule, not ours.
- SDK major versions introduce breaking changes.
- Users have different providers available, different keys, and different cost
  constraints; some can only reach a self-hosted or proxied endpoint.
- Provider calls are slow, non-deterministic, and cost money on every
  invocation - which makes them intolerable inside a test suite.

The last point is the sharpest. If a use case calls the SDK directly, testing
that use case means either paying for a real call, or mocking the internals of
the SDK - which couples the tests to the shape of the SDK and breaks on its
next major version.

## Decision

We will define an **`AIProvider` port** in the inner layers and implement it
with an adapter in `infrastructure/`.

- The port is narrow: send a request built from domain types, receive a domain
  response. It expresses what Forge needs, not what the SDK offers.
- The OpenAI SDK is imported in exactly one place: the adapter.
- The adapter owns timeouts, retries, and **exception translation**. Every SDK
  exception becomes a domain error - `ProviderTimeoutError`,
  `ProviderRateLimitError`, `ProviderAuthenticationError`,
  `ProviderUnavailableError`, `ProviderResponseError` - at that boundary. No
  SDK type crosses it.
- The test suite provides a fake implementation returning canned responses.
  Every use case is tested against the fake.
- Ruff bans `openai` and `httpx` outside `infrastructure/`.

The port is defined by the layer that needs it, and the adapter depends on the
port - not the other way round. That inversion is the point of this ADR.

## Alternatives Considered

**Call the SDK directly from use cases.** Least code, most obvious. Rejected
because it makes every use case untestable without a network call or a mock of
SDK internals, and it spreads a volatile dependency through the layer that
should be the most stable.

**Use an abstraction library (LangChain, LiteLLM, or similar).** Someone else
maintains the provider abstraction. Rejected for three reasons: it is a very
large dependency for a narrow need; it imposes its own abstractions on the
domain model; and it replaces one volatile dependency with two, since the
library tracks provider changes on its own schedule. The requirement here is
small enough that a hand-written port is smaller than the configuration needed
to drive a framework.

**Wrap the SDK in a thin utility module, without a formal port.** Cheaper than
a port, and better than nothing. Rejected because it inverts nothing: the use
case still depends on the concrete module, so a test still has to patch that
module. The seam must be an interface the inner layer owns for the inversion to
work.

**Support multiple providers immediately.** Rejected as premature. One adapter
now, behind an interface that makes the second one cheap. YAGNI applies to the
implementations, not to the seam.

## Consequences

**Easier:**

- Use cases are unit-tested with a small fake: fast, free, deterministic, and
  able to cover every failure branch.
- A second provider is one new class.
- SDK breaking changes are contained in a single file.
- Error handling is uniform, because translation happens in one place.

**Harder:**

- The port has to be kept narrow. It is tempting to widen it toward whatever
  the SDK exposes, and every such addition weakens the abstraction.
- Provider-specific features - streaming, tool calling, structured output - do
  not arrive for free. Each needs a deliberate decision about whether it
  belongs in the port at all.
- The fake must stay faithful. A fake that never fails produces tests that
  never exercise the failure paths, so it must be able to raise every
  translated error.

**Accepted:** no layer other than `infrastructure/` may import an AI SDK.
Changing this requires a new ADR.
