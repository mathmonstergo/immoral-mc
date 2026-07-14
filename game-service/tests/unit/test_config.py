import pytest
from pydantic import ValidationError

from immortal_mmo.core.config import Settings


def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "database_url",
    [
        "",
        "   ",
        "postgresql://game:test@database/game",
    ],
)
def test_settings_reject_invalid_database_urls(database_url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=database_url)


def test_settings_accept_asyncpg_database_url_and_strip_whitespace() -> None:
    settings = Settings(
        _env_file=None,
        database_url="  postgresql+asyncpg://game:test@database/game  ",
    )

    assert settings.database_url == "postgresql+asyncpg://game:test@database/game"


def test_settings_load_database_pool_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://game:test@database/game")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "12")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "24")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "8.5")
    monkeypatch.setenv("DATABASE_ECHO", "true")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://game:test@database/game"
    assert settings.database_pool_size == 12
    assert settings.database_max_overflow == 24
    assert settings.database_pool_timeout_seconds == 8.5
    assert settings.database_echo is True


def test_settings_use_bounded_pool_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://game:test@database/game")

    settings = Settings(_env_file=None)

    assert settings.database_pool_size == 5
    assert settings.database_max_overflow == 10
    assert settings.database_pool_timeout_seconds == 5.0
    assert settings.database_echo is False


@pytest.mark.parametrize(
    ("environment_name", "value"),
    [
        ("DATABASE_POOL_SIZE", "0"),
        ("DATABASE_MAX_OVERFLOW", "101"),
        ("DATABASE_POOL_TIMEOUT_SECONDS", "0"),
    ],
)
def test_settings_reject_out_of_bounds_pool_configuration(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    value: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://game:test@database/game")
    monkeypatch.setenv(environment_name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
