"""Configuration loading, and the promises it makes about secrets.

Integration rather than unit: these cross a real boundary - the process
environment and the filesystem - even though nothing here touches a network.
"""

from pathlib import Path

import pytest

from forge.domain.errors import ConfigurationError
from forge.infrastructure.config import Settings, get_settings, load_settings


@pytest.mark.integration
def test_defaults_apply_when_nothing_is_configured() -> None:
    settings = load_settings()

    assert settings.provider == "openai"
    assert settings.model == "gpt-4o-mini"
    assert settings.log_level == "INFO"
    assert settings.timeout_seconds == 60.0
    assert settings.api_key is None
    assert settings.base_url is None


@pytest.mark.integration
def test_a_blank_base_url_is_treated_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``.env.example`` documents FORGE_BASE_URL with an empty value.

    Copying that line verbatim into a real .env leaves the key present but
    blank. Without this, the blank string reaches the OpenAI SDK as an actual
    base URL and every request fails with a connection error that names
    nothing the user set - exactly what a first-run user hits by following the
    example file as given.
    """
    monkeypatch.setenv("FORGE_BASE_URL", "")

    assert load_settings().base_url is None


@pytest.mark.integration
def test_a_real_base_url_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_BASE_URL", "https://example.invalid/v1")

    assert load_settings().base_url == "https://example.invalid/v1"


@pytest.mark.integration
def test_every_value_can_be_set_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORGE_API_KEY", "test-key-value-1234")
    monkeypatch.setenv("FORGE_MODEL", "gpt-4o")
    monkeypatch.setenv("FORGE_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("FORGE_LOG_LEVEL", "debug")
    monkeypatch.setenv("FORGE_TIMEOUT_SECONDS", "12.5")

    settings = load_settings()

    assert settings.model == "gpt-4o"
    assert settings.base_url == "https://example.invalid/v1"
    assert settings.log_level == "DEBUG"
    assert settings.timeout_seconds == 12.5
    assert settings.require_api_key() == "test-key-value-1234"


@pytest.mark.integration
def test_settings_are_read_from_a_dotenv_file(tmp_path: Path) -> None:
    """A developer keeps their key in .env; the loader must find it."""
    (tmp_path / ".env").write_text(
        "FORGE_MODEL=from-dotenv\nFORGE_TIMEOUT_SECONDS=7\n", encoding="utf-8"
    )

    settings = load_settings()

    assert settings.model == "from-dotenv"
    assert settings.timeout_seconds == 7.0


@pytest.mark.integration
def test_env_example_copied_verbatim_does_not_break_the_base_url(
    tmp_path: Path,
) -> None:
    """The exact failure a user hits by following the setup guide as written.

    ``cp .env.example .env`` and filling in only the key leaves every other
    line - including ``FORGE_BASE_URL=`` - blank but present.
    """
    (tmp_path / ".env").write_text(
        "FORGE_API_KEY=not-a-real-credential-0123456789\nFORGE_BASE_URL=\n",
        encoding="utf-8",
    )

    assert load_settings().base_url is None


@pytest.mark.integration
def test_the_environment_wins_over_a_dotenv_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("FORGE_MODEL=from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_MODEL", "from-environment")

    assert load_settings().model == "from-environment"


# --- secrets ---------------------------------------------------------------


@pytest.mark.integration
def test_the_api_key_never_appears_in_repr_or_str(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The single most likely way to leak a key is printing the settings.

    The value below deliberately looks nothing like a real credential: a
    realistic-looking placeholder teaches both people and secret scanners to
    skim past the shape that matters.
    """
    fake_key = "not-a-real-credential-0123456789"
    monkeypatch.setenv("FORGE_API_KEY", fake_key)

    settings = load_settings()

    assert fake_key not in repr(settings)
    assert fake_key not in str(settings)
    assert fake_key not in str(settings.model_dump())
    assert fake_key == settings.require_api_key()


@pytest.mark.integration
def test_a_rejected_value_is_not_echoed_back_to_the_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pydantic includes the offending input in its own message. We must not.

    A user who mistypes FORGE_API_KEY into FORGE_TIMEOUT_SECONDS should not
    then see the key printed back at them in the error.
    """
    monkeypatch.setenv("FORGE_TIMEOUT_SECONDS", "not-a-real-credential-leaked-here")

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    assert "not-a-real-credential-leaked-here" not in str(caught.value)


# --- errors ----------------------------------------------------------------


@pytest.mark.integration
def test_a_missing_key_explains_which_variable_to_set() -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_settings().require_api_key()

    message = str(caught.value)
    assert "FORGE_API_KEY" in message
    assert ".env.example" in message


@pytest.mark.integration
def test_a_blank_key_is_treated_as_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_API_KEY", "   ")

    with pytest.raises(ConfigurationError, match="FORGE_API_KEY"):
        load_settings().require_api_key()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("variable", "value", "expected"),
    [
        ("FORGE_TIMEOUT_SECONDS", "0", "FORGE_TIMEOUT_SECONDS"),
        ("FORGE_TIMEOUT_SECONDS", "-5", "FORGE_TIMEOUT_SECONDS"),
        ("FORGE_TIMEOUT_SECONDS", "not-a-number", "FORGE_TIMEOUT_SECONDS"),
        ("FORGE_LOG_LEVEL", "SHOUTING", "FORGE_LOG_LEVEL"),
        ("FORGE_MODEL", "   ", "FORGE_MODEL"),
        ("FORGE_PROVIDER", "anthropic", "FORGE_PROVIDER"),
    ],
)
def test_an_invalid_value_names_the_variable_at_fault(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str, expected: str
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    assert expected in str(caught.value)


@pytest.mark.integration
def test_a_pydantic_error_never_escapes_the_infrastructure_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only ForgeError subclasses may cross this boundary."""
    monkeypatch.setenv("FORGE_TIMEOUT_SECONDS", "nonsense")

    with pytest.raises(ConfigurationError):
        load_settings()


# --- caching ---------------------------------------------------------------


@pytest.mark.integration
def test_settings_are_loaded_once_per_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORGE_MODEL", "first")
    first = get_settings()

    monkeypatch.setenv("FORGE_MODEL", "second")
    second = get_settings()

    assert first is second
    assert second.model == "first"


@pytest.mark.integration
def test_settings_are_immutable() -> None:
    settings = Settings()

    with pytest.raises(ValueError, match="frozen"):
        settings.model = "changed"
