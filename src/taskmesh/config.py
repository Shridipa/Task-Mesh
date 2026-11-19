"""Runtime configuration for TaskMesh.

This module is the single source of truth for every value TaskMesh reads from
the environment. Two rules are enforced here:

* A configured value is used verbatim. A PostgreSQL URL is never rewritten to
  SQLite (or vice versa); the only transformation is an explicit, validated
  conversion to a synchronous driver for Alembic migrations.
* Invalid configuration fails loudly at start-up with a message that names the
  variable and never contains a credential.

``get_settings()`` caches the parsed result. Tests that need a different
configuration can call ``reset_settings_cache()`` after changing the
environment.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./taskmesh.db"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_DEV_WORKER_SECRET = "dev-insecure-worker-secret"
DEFAULT_DEV_JWT_SECRET = "dev-insecure-jwt-secret-change-me"
DEV_ADMIN_API_KEY = "dev-admin-key"

# Async SQLAlchemy drivers the application can actually use. Anything else is a
# configuration error, because silently swapping in another database engine is
# exactly what this project must not do.
SUPPORTED_ASYNC_SCHEMES = ("sqlite+aiosqlite", "postgresql+asyncpg")

#: Map of async SQLAlchemy driver -> synchronous driver used by Alembic.
SYNC_DRIVER_MAP = {
    "sqlite+aiosqlite": "sqlite",
    "postgresql+asyncpg": "postgresql+psycopg2",
}

VALID_ROLES = ("admin", "developer", "viewer")


class ConfigError(RuntimeError):
    """Raised when the environment describes a configuration we cannot honour."""


def redact_url(url: str) -> str:
    """Return ``url`` with any password replaced by ``***``.

    Used whenever a database or Redis URL is logged so credentials never reach
    log output.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<unparsable-url>"
    if parts.password is None:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    netloc = f"{parts.username or ''}:***@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def to_sync_url(url: str) -> str:
    """Convert an async SQLAlchemy URL into the sync URL Alembic needs.

    Raises ``ConfigError`` for any driver we do not know how to map, instead of
    guessing.
    """
    scheme = url.split("://", 1)[0]
    if scheme not in SYNC_DRIVER_MAP:
        raise ConfigError(
            f"DATABASE_URL uses unsupported driver '{scheme}'. "
            f"Supported async drivers: {', '.join(SUPPORTED_ASYNC_SCHEMES)}"
        )
    return SYNC_DRIVER_MAP[scheme] + "://" + url.split("://", 1)[1]


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean, got {raw!r}")


def _parse_api_keys(raw: str | None, environment: str) -> dict[str, tuple[str, str]]:
    """Parse ``key:role:tenant,key2:role:tenant`` into a mapping."""
    keys: dict[str, tuple[str, str]] = {}
    if not raw:
        if environment == "production":
            raise ConfigError(
                "AUTH_API_KEYS must be configured in production. "
                "Format: key:role:tenant,key2:role:tenant"
            )
        return keys

    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) not in (2, 3):
            raise ConfigError(
                "AUTH_API_KEYS entries must be 'key:role' or 'key:role:tenant'"
            )
        key, role = parts[0].strip(), parts[1].strip()
        tenant = parts[2].strip() if len(parts) == 3 else "default"
        if len(key) < 8:
            raise ConfigError("AUTH_API_KEYS keys must be at least 8 characters long")
        if role not in VALID_ROLES:
            raise ConfigError(
                f"AUTH_API_KEYS role must be one of {', '.join(VALID_ROLES)}, got {role!r}"
            )
        keys[key] = (role, tenant)
    return keys


def _parse_origins(raw: str | None, environment: str) -> tuple[str, ...]:
    origins = tuple(o.strip() for o in (raw or "").split(",") if o.strip())
    if environment == "production":
        if not origins:
            raise ConfigError(
                "CORS_ORIGINS must list the allowed front-end origins in production"
            )
        if "*" in origins:
            raise ConfigError(
                "CORS_ORIGINS must not contain '*' in production; list explicit origins"
            )
    return origins


@dataclass(frozen=True)
class Settings:
    """Immutable, validated view of the environment."""

    environment: str
    database_url: str
    redis_url: str
    auto_create_schema: bool
    db_pool_size: int
    db_max_overflow: int
    db_pool_timeout: int
    db_pool_recycle: int
    cors_origins: tuple[str, ...]
    worker_secret: str
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    jwt_ttl_seconds: int
    api_keys: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    embedded_worker: bool = True
    embedded_scheduler: bool = True
    worker_lease_seconds: int = 900
    job_poll_seconds: float = 1.0
    worker_health_file: str | None = None
    scheduler_health_file: str | None = None
    max_request_bytes: int = 2 * 1024 * 1024
    rate_limit_submissions: int = 10
    rate_limit_window_seconds: int = 60
    log_level: str = "INFO"
    log_format: str = "text"
    metrics_public: bool = False

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.split("://", 1)[0].startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def redis_required(self) -> bool:
        """Redis is a cache/lock, not a source of truth, but production needs it."""
        return self.is_production


def load_settings() -> Settings:
    """Build a :class:`Settings` from the current process environment."""
    return _load_from_env()


def _load_from_env() -> Settings:
    environment = (_env("ENVIRONMENT", "development") or "development").lower()
    if environment not in {"development", "production", "test"}:
        raise ConfigError(
            "ENVIRONMENT must be one of development, production, test; "
            f"got {environment!r}"
        )
    is_production = environment == "production"

    database_url = _env("DATABASE_URL", DEFAULT_DATABASE_URL) or DEFAULT_DATABASE_URL
    scheme = database_url.split("://", 1)[0] if "://" in database_url else ""
    if scheme not in SUPPORTED_ASYNC_SCHEMES:
        raise ConfigError(
            "DATABASE_URL must use a supported async driver "
            f"({', '.join(SUPPORTED_ASYNC_SCHEMES)}); got scheme {scheme!r}. "
            "TaskMesh will not silently substitute a different database."
        )

    redis_url = _env("REDIS_URL", DEFAULT_REDIS_URL) or DEFAULT_REDIS_URL

    worker_secret = _env("WORKER_SECRET")
    if not worker_secret:
        if is_production:
            raise ConfigError("WORKER_SECRET must be set in production")
        worker_secret = DEFAULT_DEV_WORKER_SECRET

    jwt_secret = _env("AUTH_JWT_SECRET") or _env("JWT_SECRET")
    if not jwt_secret:
        if is_production:
            raise ConfigError("AUTH_JWT_SECRET must be set in production")
        jwt_secret = DEFAULT_DEV_JWT_SECRET
    if is_production and len(jwt_secret) < 32:
        raise ConfigError("AUTH_JWT_SECRET must be at least 32 characters in production")

    api_keys = dict(_parse_api_keys(_env("AUTH_API_KEYS"), environment))
    if not api_keys and not is_production:
        # Local development convenience: a documented, loudly-logged dev key.
        api_keys[DEV_ADMIN_API_KEY] = ("admin", "default")

    cors_raw = _env("CORS_ALLOWED_ORIGINS") or _env("CORS_ORIGINS")
    if cors_raw is None and not is_production:
        cors_raw = "http://localhost:3000,http://localhost:5173"
    cors_origins = _parse_origins(cors_raw, environment)

    default_auto_schema = not is_production
    auto_create_schema = _env_bool("AUTO_CREATE_SCHEMA", default_auto_schema)

    log_format = (_env("LOG_FORMAT", "text") or "text").lower()
    if log_format not in {"text", "json"}:
        raise ConfigError("LOG_FORMAT must be 'text' or 'json'")

    return Settings(
        environment=environment,
        database_url=database_url,
        redis_url=redis_url,
        auto_create_schema=auto_create_schema,
        db_pool_size=_env_int("DB_POOL_SIZE", 10, minimum=1),
        db_max_overflow=_env_int("DB_MAX_OVERFLOW", 20),
        db_pool_timeout=_env_int("DB_POOL_TIMEOUT", 30, minimum=1),
        db_pool_recycle=_env_int("DB_POOL_RECYCLE", 1800, minimum=1),
        cors_origins=cors_origins,
        worker_secret=worker_secret,
        jwt_secret=jwt_secret,
        jwt_issuer=_env("AUTH_JWT_ISSUER", "taskmesh") or "taskmesh",
        jwt_audience=_env("AUTH_JWT_AUDIENCE", "taskmesh-api") or "taskmesh-api",
        jwt_ttl_seconds=_env_int("AUTH_TOKEN_TTL_SECONDS", 3600, minimum=60),
        api_keys=api_keys,
        embedded_worker=_env_bool("EMBEDDED_WORKER", True),
        embedded_scheduler=_env_bool("EMBEDDED_SCHEDULER", True),
        worker_lease_seconds=_env_int("WORKER_LEASE_SECONDS", 900, minimum=30),
        job_poll_seconds=float(_env("JOB_POLL_SECONDS", "1") or 1),
        worker_health_file=_env("WORKER_HEALTH_FILE"),
        scheduler_health_file=_env("SCHEDULER_HEALTH_FILE"),
        max_request_bytes=_env_int("MAX_REQUEST_BYTES", 2 * 1024 * 1024, minimum=1024),
        rate_limit_submissions=_env_int("RATE_LIMIT_SUBMISSIONS", 10, minimum=1),
        rate_limit_window_seconds=_env_int("RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1),
        log_level=(_env("LOG_LEVEL", "INFO") or "INFO").upper(),
        log_format=log_format,
        metrics_public=_env_bool("METRICS_PUBLIC", False),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""
    return _load_from_env()


def reset_settings_cache() -> None:
    """Clear the settings cache (used by tests and by configuration reloads)."""
    get_settings.cache_clear()
