"""Logging setup, with secrets redacted at the sink.

Loguru is imported here and nowhere else. The inner layers do not log today;
when one needs to, it will depend on a small port rather than on this module.

The redaction deliberately happens **in the sink**, not at each call site. A
rule that every caller must remember to apply is a rule that will eventually be
forgotten - and the one time it is forgotten, a key is on someone's terminal
and in their scrollback. Filtering the one place every message passes through
makes the guarantee structural instead of cultural.
"""

import sys
from collections.abc import Callable, Iterable
from typing import TextIO

from loguru import logger

REDACTED = "***REDACTED***"

_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan> - <level>{message}</level>"
)

# Shortest string still worth hiding. Redacting a one- or two-character value
# would replace half the alphabet in every log line and reveal nothing useful.
_MIN_SECRET_LENGTH = 8


def _redacting_sink(stream: TextIO, secrets: tuple[str, ...]) -> Callable[[str], None]:
    """Wrap ``stream`` so that no known secret can reach it."""

    def sink(message: str) -> None:
        text = message
        for secret in secrets:
            text = text.replace(secret, REDACTED)
        stream.write(text)

    return sink


def configure_logging(
    level: str = "INFO",
    *,
    secrets: Iterable[str] = (),
    stream: TextIO | None = None,
) -> None:
    """Send logs to stderr at ``level``, redacting every value in ``secrets``.

    Logs go to stderr so that stdout stays clean for results - a user piping
    Forge into another command should get output, not diagnostics.

    Args:
        level: Minimum severity to emit.
        secrets: Values to replace wherever they appear in a message. Short
            values are ignored, since redacting them would corrupt the output
            without protecting anything.
        stream: Where to write. Defaults to stderr; tests pass their own.
    """
    redactable = tuple(
        secret for secret in secrets if secret and len(secret) >= _MIN_SECRET_LENGTH
    )

    logger.remove()
    logger.add(
        _redacting_sink(stream if stream is not None else sys.stderr, redactable),
        level=level.upper(),
        format=_FORMAT,
        colorize=False,
        backtrace=False,
        # Never include local variables in a traceback: they are exactly where
        # a credential would be sitting when something fails.
        diagnose=False,
    )
