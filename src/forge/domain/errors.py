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


class SourceError(ForgeError):
    """A file could not be used as input.

    Every subclass means the same thing to a caller - the input is unusable,
    exit code 2 per ADR-0006 - but they are distinct so that a message can be
    specific about which of the four ways it failed.
    """


class SourceNotFoundError(SourceError):
    """Nothing exists at the given path."""


class SourceUnreadableError(SourceError):
    """The path exists but cannot be used as source.

    A directory, a device, a permissions failure, an undecodable byte stream,
    or a file with nothing in it.
    """


class SourceTooLargeError(SourceError):
    """The file exceeds the configured size limit.

    Refused rather than truncated. Analysing the first half of a file and
    reporting on it as if it were whole produces confident nonsense.
    """


class PathOutsideWorkspaceError(SourceError):
    """The path resolves outside the workspace.

    Forge reads what you point it at, inside the directory you are working in.
    Following a path - or a symlink - out of that directory is how a tool that
    sends code to a third party turns into a way to exfiltrate it.
    """


class RepositoryError(ForgeError):
    """The repository could not answer what was asked of it.

    Like :class:`SourceError`, every subclass means "the request cannot be
    satisfied as asked" to a caller - exit code 2 per ADR-0006 - but they are
    distinct so a message can be specific about why.
    """


class NotARepositoryError(RepositoryError):
    """The working directory is not inside a git repository.

    A normal thing to be, not a fault. Only the commands that need history
    care, and they say so rather than failing obscurely.
    """


class NoChangesError(RepositoryError):
    """The file has no uncommitted changes to analyse.

    Reported rather than silently analysing the whole file: a user who asked
    about their change should not be billed for a full-file review they did
    not request.
    """


class ReviewTooLargeError(RepositoryError):
    """The planned multi-file request exceeds its accepted byte limit."""


class SensitiveContentError(RepositoryError):
    """Review was refused because selected source matched a secret rule."""


class NoHistoryError(RepositoryError):
    """The file has no history for the repository to report.

    Git has never seen it, or it sits outside the repository. Unlike its
    siblings this one is not normally shown to a user: history annotates an
    analysis that has already succeeded, so the caller degrades to showing none
    rather than failing a run that worked.
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
