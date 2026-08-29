"""The error vocabulary shared by every layer.

These live in the domain because they are part of the contract between the
inner layers and the outside world: a use case raises them, and the CLI maps
them to exit codes. An adapter translates whatever its SDK raises into one of
these at its boundary, so no third-party exception type ever escapes
:mod:`forge.infrastructure`.

Every message is written for the person who has to fix the problem. It says
what happened and, where there is one, what to do next.
"""


class ForgeError(Exception):
    """Base for every error Forge raises deliberately.

    Catching this catches everything Forge knows how to explain. Anything that
    escapes as a different type is a bug, not a user error.
    """


class ConfigurationError(ForgeError):
    """Forge is not configured well enough to do what was asked.

    Raised while loading settings, or when a required value is missing at the
    point of use. The message names the environment variable to set.
    """


class ProviderError(ForgeError):
    """The AI provider could not be used successfully.

    The subclasses distinguish the cases a user acts on differently: wait,
    fix a credential, or report a bug.
    """


class ProviderTimeoutError(ProviderError):
    """The provider did not respond within the configured timeout."""


class ProviderRateLimitError(ProviderError):
    """The provider rejected the request because of a rate or quota limit."""


class ProviderAuthenticationError(ProviderError):
    """The provider rejected the credentials."""


class ProviderUnavailableError(ProviderError):
    """The provider could not be reached, or failed on its own side."""


class ProviderResponseError(ProviderError):
    """The provider replied, but not with something Forge can use.

    Model output is untrusted input, so reaching this class is normal
    operation rather than an internal fault: it means validation did its job.
    """
