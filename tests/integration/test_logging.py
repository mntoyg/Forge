"""Logging setup, and the guarantee that a secret cannot reach the terminal.

Integration rather than unit: these configure the real Loguru logger and read
back what it actually wrote.
"""

import io

import pytest
from loguru import logger

from forge.infrastructure.logging import REDACTED, configure_logging

FAKE_KEY = "not-a-real-credential-0123456789"


@pytest.fixture
def captured() -> io.StringIO:
    """A stream standing in for stderr."""
    return io.StringIO()


@pytest.mark.integration
def test_messages_are_written_at_or_above_the_configured_level(
    captured: io.StringIO,
) -> None:
    configure_logging("WARNING", stream=captured)

    logger.debug("invisible")
    logger.warning("visible")

    output = captured.getvalue()
    assert "invisible" not in output
    assert "visible" in output


@pytest.mark.integration
def test_the_level_is_accepted_in_any_case(captured: io.StringIO) -> None:
    configure_logging("debug", stream=captured)

    logger.debug("shown")

    assert "shown" in captured.getvalue()


@pytest.mark.integration
def test_a_known_secret_is_redacted_wherever_it_appears(
    captured: io.StringIO,
) -> None:
    """Redaction happens at the sink, so no caller has to remember it."""
    configure_logging("INFO", secrets=[FAKE_KEY], stream=captured)

    logger.info("Calling the provider with key {}", FAKE_KEY)

    output = captured.getvalue()
    assert FAKE_KEY not in output
    assert REDACTED in output


@pytest.mark.integration
def test_a_secret_is_redacted_even_when_it_arrives_inside_an_exception(
    captured: io.StringIO,
) -> None:
    """The most likely accidental leak is a traceback, not a log call."""
    configure_logging("ERROR", secrets=[FAKE_KEY], stream=captured)

    try:
        raise RuntimeError(f"request failed for {FAKE_KEY}")
    except RuntimeError:
        logger.exception("provider call failed")

    output = captured.getvalue()
    assert FAKE_KEY not in output
    assert REDACTED in output


@pytest.mark.integration
def test_local_variables_are_never_included_in_a_traceback(
    captured: io.StringIO,
) -> None:
    """Loguru's diagnose mode prints locals - which is where a key would be."""
    configure_logging("ERROR", stream=captured)

    def fails() -> None:
        credential_in_scope = FAKE_KEY  # noqa: F841 - the point of the test
        raise RuntimeError("boom")

    try:
        fails()
    except RuntimeError:
        logger.exception("failed")

    assert FAKE_KEY not in captured.getvalue()


@pytest.mark.integration
@pytest.mark.parametrize("too_short", ["", "a", "abc", "1234567"])
def test_a_value_too_short_to_be_a_secret_is_left_alone(
    captured: io.StringIO, too_short: str
) -> None:
    """Redacting a short string would corrupt every line and protect nothing."""
    configure_logging("INFO", secrets=[too_short], stream=captured)

    logger.info("a message about abc and 1234567")

    assert REDACTED not in captured.getvalue()


@pytest.mark.integration
def test_several_secrets_are_all_redacted(captured: io.StringIO) -> None:
    other = "another-fake-credential-987654"
    configure_logging("INFO", secrets=[FAKE_KEY, other], stream=captured)

    logger.info("{} and {}", FAKE_KEY, other)

    output = captured.getvalue()
    assert FAKE_KEY not in output
    assert other not in output
    assert output.count(REDACTED) == 2


@pytest.mark.integration
def test_configuring_twice_does_not_duplicate_output(captured: io.StringIO) -> None:
    """A second call must replace the sink, not add another one."""
    configure_logging("INFO", stream=captured)
    configure_logging("INFO", stream=captured)

    logger.info("once")

    assert captured.getvalue().count("once") == 1
