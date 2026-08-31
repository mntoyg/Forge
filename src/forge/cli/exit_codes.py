"""The exit code contract, and the one place errors are mapped onto it.

ADR-0006 makes these numbers a public interface: scripts branch on them, so
moving a meaning between codes is a breaking change.

Mapping lives here and nowhere else. The domain raises typed errors and knows
nothing about exit codes; this module is the single translation point, which is
what keeps the table honest as new error classes appear.
"""

from enum import IntEnum

from forge.domain.errors import (
    ConfigurationError,
    ForgeError,
    ProviderError,
    ProviderResponseError,
    RepositoryError,
    SourceError,
)


class ExitCode(IntEnum):
    """See ADR-0006. These values are a public contract."""

    OK = 0
    """The command did what was asked - findings or not."""

    FAILED = 1
    """It ran but could not produce a result."""

    BAD_INPUT = 2
    """The input was unusable: missing, unreadable, too large, out of bounds."""

    NOT_CONFIGURED = 3
    """Forge is not configured well enough to run."""

    PROVIDER_FAILED = 4
    """The provider timed out, refused, or could not be reached."""


def exit_code_for(error: ForgeError) -> ExitCode:
    """Map a Forge error to its exit code.

    Ordered most specific first. Anything unclassified becomes ``FAILED``
    rather than a new code, per ADR-0006: a wide table invites codes nobody
    handles.
    """
    # A repository problem joins SourceError rather than taking a code of its
    # own: to a caller, "no such file" and "no changes to review" are the same
    # class of answer - the request cannot be satisfied as asked. ADR-0006
    # warns that a wide table invites codes nobody handles.
    if isinstance(error, SourceError | RepositoryError):
        return ExitCode.BAD_INPUT
    if isinstance(error, ConfigurationError):
        return ExitCode.NOT_CONFIGURED
    # Checked before ProviderError, which it subclasses. An unparseable reply
    # means the provider worked and Forge could not use the answer - a
    # different problem from the provider failing, and a different reaction:
    # retrying a timeout is sensible, retrying this is usually not.
    if isinstance(error, ProviderResponseError):
        return ExitCode.FAILED
    if isinstance(error, ProviderError):
        return ExitCode.PROVIDER_FAILED
    return ExitCode.FAILED
