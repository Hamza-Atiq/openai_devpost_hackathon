"""Strict, portable environment configuration for server-owned values."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Raised when environment configuration crosses a declared boundary."""


class RuntimeEnvironment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PREVIEW = "preview"
    PRODUCTION = "production"


_KNOWN_CRICKOPS_NAMES = frozenset(
    {
        "CRICKOPS_ENV",
        "CRICKOPS_LIVE_SERVICES_ENABLED",
        "CRICKOPS_COOKIE_SECRET",
        "CRICKOPS_ENCRYPTION_SECRET",
        "CRICKOPS_ALLOWED_FRONTEND_ORIGINS",
    }
)
_DEPLOYED_ENVIRONMENTS = frozenset(
    {RuntimeEnvironment.PREVIEW, RuntimeEnvironment.PRODUCTION}
)


def _optional_value(environment: Mapping[str, str], name: str) -> str | None:
    value = environment.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _strict_boolean(environment: Mapping[str, str], name: str, *, default: bool) -> bool:
    value = _optional_value(environment, name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized not in {"true", "false"}:
        raise ConfigurationError(f"{name} must be either true or false")
    return normalized == "true"


def _validate_database_url(value: str | None, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ConfigurationError("DATABASE_URL is required in this runtime environment")
        return None
    if urlsplit(value).scheme not in {"postgres", "postgresql"}:
        raise ConfigurationError("DATABASE_URL must use postgres:// or postgresql://")
    return value


def _validate_secret(value: str | None, name: str, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ConfigurationError(f"{name} is required in this runtime environment")
        return None
    if len(value) < 32:
        raise ConfigurationError(f"{name} must contain at least 32 characters")
    return value


def _validate_provider_key(value: str | None, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ConfigurationError("OPENAI_API_KEY is required in this runtime environment")
        return None
    if len(value) < 16:
        raise ConfigurationError("OPENAI_API_KEY is malformed")
    return value


def _validate_origins(value: str | None, *, required: bool) -> tuple[str, ...]:
    if value is None:
        if required:
            raise ConfigurationError(
                "CRICKOPS_ALLOWED_FRONTEND_ORIGINS is required in this runtime environment"
            )
        return ()

    origins = tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())
    if not origins:
        raise ConfigurationError("CRICKOPS_ALLOWED_FRONTEND_ORIGINS must not be empty")
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise ConfigurationError(
                "CRICKOPS_ALLOWED_FRONTEND_ORIGINS must contain HTTPS origins only"
            )
    return origins


@dataclass(frozen=True, slots=True)
class ServerSettings:
    environment: RuntimeEnvironment
    live_services_enabled: bool
    database_url: str | None = field(repr=False)
    openai_api_key: str | None = field(repr=False)
    cookie_secret: str | None = field(repr=False)
    encryption_secret: str | None = field(repr=False)
    allowed_frontend_origins: tuple[str, ...]

    @classmethod
    def from_env(cls, environment: Mapping[str, str] | None = None) -> ServerSettings:
        values = os.environ if environment is None else environment
        unknown_names = sorted(
            name
            for name in values
            if name.startswith("CRICKOPS_") and name not in _KNOWN_CRICKOPS_NAMES
        )
        if unknown_names:
            raise ConfigurationError(f"Unknown CrickOps environment variable: {unknown_names[0]}")

        environment_name = _optional_value(values, "CRICKOPS_ENV")
        try:
            runtime = RuntimeEnvironment(environment_name or "")
        except ValueError as error:
            raise ConfigurationError(
                "CRICKOPS_ENV must be one of local, test, preview, or production"
            ) from error

        deployed = runtime in _DEPLOYED_ENVIRONMENTS
        live_services_enabled = _strict_boolean(
            values,
            "CRICKOPS_LIVE_SERVICES_ENABLED",
            default=deployed,
        )
        if deployed and not live_services_enabled:
            raise ConfigurationError(
                "CRICKOPS_LIVE_SERVICES_ENABLED cannot be false in preview or production"
            )

        live_values_required = deployed or live_services_enabled
        database_url = _validate_database_url(
            _optional_value(values, "DATABASE_URL"),
            required=live_values_required,
        )
        openai_api_key = _validate_provider_key(
            _optional_value(values, "OPENAI_API_KEY"),
            required=live_values_required,
        )

        return cls(
            environment=runtime,
            live_services_enabled=live_services_enabled,
            database_url=database_url,
            openai_api_key=openai_api_key,
            cookie_secret=_validate_secret(
                _optional_value(values, "CRICKOPS_COOKIE_SECRET"),
                "CRICKOPS_COOKIE_SECRET",
                required=deployed,
            ),
            encryption_secret=_validate_secret(
                _optional_value(values, "CRICKOPS_ENCRYPTION_SECRET"),
                "CRICKOPS_ENCRYPTION_SECRET",
                required=deployed,
            ),
            allowed_frontend_origins=_validate_origins(
                _optional_value(values, "CRICKOPS_ALLOWED_FRONTEND_ORIGINS"),
                required=deployed,
            ),
        )
