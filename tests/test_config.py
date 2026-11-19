"""Configuration tests: URL handling, validation and secret hygiene."""

from __future__ import annotations

import pytest

from taskmesh.config import (
    DEV_ADMIN_API_KEY,
    ConfigError,
    load_settings,
    redact_url,
    reset_settings_cache,
    to_sync_url,
)

ENV_VARS = (
    "DATABASE_URL",
    "REDIS_URL",
    "ENVIRONMENT",
    "WORKER_SECRET",
    "AUTH_JWT_SECRET",
    "JWT_SECRET",
    "AUTH_API_KEYS",
    "CORS_ORIGINS",
    "CORS_ALLOWED_ORIGINS",
    "AUTO_CREATE_SCHEMA",
    "LOG_FORMAT",
    "EMBEDDED_WORKER",
    "EMBEDDED_SCHEDULER",
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """Run each test with a clean TaskMesh environment and a fresh cache."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def _settings(**env: str):
    """Load settings from exactly ``env`` and restore the environment afterwards."""
    import os

    saved = {name: os.environ.get(name) for name in ENV_VARS}
    try:
        for name in ENV_VARS:
            os.environ.pop(name, None)
        os.environ.update(env)
        reset_settings_cache()
        return load_settings()
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        reset_settings_cache()


def test_postgres_url_is_never_rewritten_to_sqlite():
    url = "postgresql+asyncpg://taskmesh:secret@db.internal:5432/taskmesh"

    settings = _settings(DATABASE_URL=url, ENVIRONMENT="test")

    assert settings.database_url == url
    assert settings.is_sqlite is False


def test_sqlite_is_the_documented_development_default():
    settings = _settings(ENVIRONMENT="test")

    assert settings.database_url.startswith("sqlite+aiosqlite://")
    assert settings.is_sqlite is True
    assert settings.auto_create_schema is True


def test_unsupported_drivers_fail_loudly():
    with pytest.raises(ConfigError, match="async"):
        _settings(DATABASE_URL="postgresql://user:pass@localhost/taskmesh")
    with pytest.raises(ConfigError, match="async"):
        _settings(DATABASE_URL="mysql+pymysql://user:pass@localhost/taskmesh")


def test_sync_url_conversion_for_migrations():
    assert (
        to_sync_url("postgresql+asyncpg://user:pass@localhost:5432/taskmesh")
        == "postgresql+psycopg2://user:pass@localhost:5432/taskmesh"
    )
    assert to_sync_url("sqlite+aiosqlite:///./dev.db") == "sqlite:///./dev.db"
    with pytest.raises(ConfigError):
        to_sync_url("mysql+aiomysql://localhost/db")


def test_redacted_urls_never_contain_the_password():
    redacted = redact_url("postgresql+asyncpg://taskmesh:hunter2@db.internal:5432/taskmesh")

    assert "hunter2" not in redacted
    assert "taskmesh:***@db.internal:5432" in redacted
    # URLs without a password are unchanged.
    assert redact_url("sqlite+aiosqlite:///./dev.db") == "sqlite+aiosqlite:///./dev.db"


def test_production_requires_explicit_secrets_and_origins():
    with pytest.raises(ConfigError, match="AUTH_API_KEYS"):
        _settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://u:p@db:5432/taskmesh",
            WORKER_SECRET="x" * 32,
            AUTH_JWT_SECRET="y" * 32,
            CORS_ORIGINS="https://app.example.com",
        )

    with pytest.raises(ConfigError, match="CORS_ORIGINS"):
        _settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://u:p@db:5432/taskmesh",
            WORKER_SECRET="x" * 32,
            AUTH_JWT_SECRET="y" * 32,
            AUTH_API_KEYS="production-admin-key:admin:default",
        )


def test_production_rejects_wildcard_cors():
    with pytest.raises(ConfigError, match="\\*"):
        _settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://u:p@db:5432/taskmesh",
            WORKER_SECRET="x" * 32,
            AUTH_JWT_SECRET="y" * 32,
            AUTH_API_KEYS="production-admin-key:admin:default",
            CORS_ORIGINS="*",
        )


def test_production_rejects_short_jwt_secrets_and_default_worker_secret():
    base = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql+asyncpg://u:p@db:5432/taskmesh",
        "AUTH_API_KEYS": "production-admin-key:admin:default",
        "CORS_ORIGINS": "https://app.example.com",
    }
    with pytest.raises(ConfigError, match="AUTH_JWT_SECRET"):
        _settings(**base, WORKER_SECRET="x" * 32, AUTH_JWT_SECRET="too-short")
    with pytest.raises(ConfigError, match="WORKER_SECRET"):
        _settings(**base, AUTH_JWT_SECRET="y" * 32)


def test_development_gets_a_documented_dev_key():
    settings = _settings(ENVIRONMENT="development")

    assert settings.api_keys[DEV_ADMIN_API_KEY] == ("admin", "default")
    assert settings.cors_origins == ("http://localhost:3000", "http://localhost:5173")


def test_api_key_entries_are_validated():
    settings = _settings(
        ENVIRONMENT="test",
        AUTH_API_KEYS="first-key:admin:tenant-a,second-key:viewer",
    )
    assert settings.api_keys == {
        "first-key": ("admin", "tenant-a"),
        "second-key": ("viewer", "default"),
    }

    with pytest.raises(ConfigError, match="role"):
        _settings(ENVIRONMENT="test", AUTH_API_KEYS="a-long-enough-key:superuser")
    with pytest.raises(ConfigError, match="at least 8"):
        _settings(ENVIRONMENT="test", AUTH_API_KEYS="tiny:admin")


def test_production_does_not_auto_create_schema():
    settings = _settings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+asyncpg://u:p@db:5432/taskmesh",
        WORKER_SECRET="x" * 32,
        AUTH_JWT_SECRET="y" * 32,
        AUTH_API_KEYS="production-admin-key:admin:default",
        CORS_ORIGINS="https://app.example.com",
    )

    assert settings.auto_create_schema is False


def test_invalid_boolean_and_log_format_are_rejected():
    with pytest.raises(ConfigError, match="boolean"):
        _settings(ENVIRONMENT="test", EMBEDDED_WORKER="maybe")
    with pytest.raises(ConfigError, match="LOG_FORMAT"):
        _settings(ENVIRONMENT="test", LOG_FORMAT="xml")
