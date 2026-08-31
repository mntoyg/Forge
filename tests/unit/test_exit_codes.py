"""The exit code contract from ADR-0006.

These numbers are a public interface: a script, a CI step, or a git hook
branches on them, and moving a meaning between codes breaks all three silently.
Pinning the values here is what makes that change loud.
"""

import pytest

from forge.cli.exit_codes import ExitCode, exit_code_for
from forge.domain.errors import (
    ConfigurationError,
    ForgeError,
    PathOutsideWorkspaceError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SourceNotFoundError,
    SourceTooLargeError,
    SourceUnreadableError,
)


@pytest.mark.unit
def test_the_published_numbers_do_not_move() -> None:
    """Changing any of these is a breaking change, not a refactor."""
    assert ExitCode.OK.value == 0
    assert ExitCode.FAILED.value == 1
    assert ExitCode.BAD_INPUT.value == 2
    assert ExitCode.NOT_CONFIGURED.value == 3
    assert ExitCode.PROVIDER_FAILED.value == 4


@pytest.mark.unit
@pytest.mark.parametrize(
    "error",
    [
        SourceNotFoundError("missing"),
        SourceUnreadableError("binary"),
        SourceTooLargeError("too big"),
        PathOutsideWorkspaceError("escaped"),
    ],
)
def test_every_input_problem_maps_to_two(error: ForgeError) -> None:
    assert exit_code_for(error) is ExitCode.BAD_INPUT


@pytest.mark.unit
def test_a_configuration_problem_maps_to_three() -> None:
    assert exit_code_for(ConfigurationError("no key")) is ExitCode.NOT_CONFIGURED


@pytest.mark.unit
@pytest.mark.parametrize(
    "error",
    [
        ProviderTimeoutError("timed out"),
        ProviderRateLimitError("slow down"),
        ProviderAuthenticationError("rejected"),
        ProviderUnavailableError("unreachable"),
    ],
)
def test_every_provider_failure_maps_to_four(error: ForgeError) -> None:
    """One code, because the caller's reaction to all four is the same."""
    assert exit_code_for(error) is ExitCode.PROVIDER_FAILED


@pytest.mark.unit
def test_an_unusable_reply_maps_to_one_not_four() -> None:
    """It subclasses ProviderError but is a different problem.

    The provider worked; Forge could not use the answer. Retrying a timeout is
    sensible, retrying this usually is not - so the codes must differ.
    """
    assert exit_code_for(ProviderResponseError("not JSON")) is ExitCode.FAILED


@pytest.mark.unit
def test_an_unclassified_error_maps_to_one() -> None:
    """ADR-0006: a wide table invites codes nobody handles."""
    assert exit_code_for(ForgeError("something else")) is ExitCode.FAILED


@pytest.mark.unit
def test_every_error_class_has_a_code() -> None:
    """A new error class must not silently fall through to a wrong number."""
    for error_class in _all_subclasses(ForgeError):
        assert isinstance(exit_code_for(error_class("x")), ExitCode)


def _all_subclasses(base: type[ForgeError]) -> list[type[ForgeError]]:
    found: list[type[ForgeError]] = []
    for subclass in base.__subclasses__():
        found.append(subclass)
        found.extend(_all_subclasses(subclass))
    return found
