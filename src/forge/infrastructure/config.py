"""Typed configuration, loaded from the environment.

Configuration is infrastructure: it is how this process happens to be told
about the outside world. The inner layers receive plain values, never this
object, so nothing inward knows that Pydantic or an ``.env`` file exist.

Two rules govern everything here, and both have tests:

1. The API key is a :class:`~pydantic.SecretStr`. It is never rendered by
   ``repr``, ``str``, logging, or an error message - reading it requires an
   explicit call.
2. A configuration problem raises
   :class:`~forge.domain.errors.ConfigurationError` with a message naming the
   variable to set. A Pydantic ``ValidationError`` never escapes this module.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from forge.domain.errors import ConfigurationError
from forge.infrastructure.source import DEFAULT_MAX_BYTES

LOG_LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")


class Settings(BaseSettings):
    """Every value Forge reads from the environment.

    Keys are prefixed ``FORGE_``; see ``.env.example`` for the full list.
    """

    model_config = SettingsConfigDict(
        env_prefix="FORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    api_key: SecretStr | None = Field(
        default=None,
        description="Credential for the configured provider.",
    )
    provider: Literal["openai"] = Field(
        default="openai",
        description="Which provider adapter to use.",
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="Model identifier passed to the provider.",
    )
    base_url: str | None = Field(
        default=None,
        description="Override for self-hosted or proxied endpoints.",
    )
    log_level: str = Field(
        default="INFO",
        description="Minimum severity written to stderr.",
    )
    timeout_seconds: float = Field(
        default=60.0,
        description="How long to wait for a provider response.",
    )
    max_file_bytes: int = Field(
        default=DEFAULT_MAX_BYTES,
        description="Largest source file Forge will analyse.",
    )

    @field_validator("log_level")
    @classmethod
    def _known_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in LOG_LEVELS:
            raise ValueError(f"must be one of {', '.join(LOG_LEVELS)}")
        return level

    @field_validator("timeout_seconds")
    @classmethod
    def _positive_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return value

    @field_validator("max_file_bytes")
    @classmethod
    def _positive_size_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least 1")
        return value

    @field_validator("model")
    @classmethod
    def _non_empty_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    def require_api_key(self) -> str:
        """Return the API key, or explain how to provide one.

        Kept separate from loading so that commands which need no provider -
        ``forge --version``, help - work with no credential configured at all.
        """
        if self.api_key is None or not self.api_key.get_secret_value().strip():
            raise ConfigurationError(
                "No API key configured. Set FORGE_API_KEY in your environment "
                "or in a .env file. See .env.example."
            )
        return self.api_key.get_secret_value()


def load_settings() -> Settings:
    """Read settings from the environment.

    Raises:
        ConfigurationError: a value is missing or invalid. The message names
            the environment variable and what is wrong with it, because a
            Pydantic traceback tells a user nothing they can act on.
    """
    try:
        return Settings()
    except ValidationError as error:
        raise ConfigurationError(_explain(error)) from error


def _explain(error: ValidationError) -> str:
    """Turn a ValidationError into something a user can act on.

    Only the field name and the reason are used. Pydantic includes the
    offending input in its own rendering, which would print a rejected API key
    to the terminal.
    """
    problems = [
        f"  FORGE_{'_'.join(str(part) for part in item['loc']).upper()}: {item['msg']}"
        for item in error.errors()
    ]
    return "Invalid configuration:\n" + "\n".join(problems)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process.

    Caching is what makes it safe for the composition root to ask for settings
    wherever it needs them without re-reading the environment. Tests clear the
    cache; see ``tests/conftest.py``.
    """
    return load_settings()
