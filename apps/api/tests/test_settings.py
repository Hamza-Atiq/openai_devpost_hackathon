from __future__ import annotations

import pytest
from app.settings import ConfigurationError, RuntimeEnvironment, ServerSettings

PRODUCTION_ENV = {
    "CRICKOPS_ENV": "production",
    "DATABASE_URL": "postgresql://crickops:password@db.example/crickops",
    "OPENAI_API_KEY": "sk-production-fixture-value",
    "CRICKOPS_COOKIE_SECRET": "c" * 32,
    "CRICKOPS_ENCRYPTION_SECRET": "e" * 32,
    "CRICKOPS_ALLOWED_FRONTEND_ORIGINS": "https://crickops.example",
}


def test_production_rejects_each_missing_server_value() -> None:
    for name in PRODUCTION_ENV:
        if name == "CRICKOPS_ENV":
            continue

        environment = PRODUCTION_ENV | {name: ""}

        with pytest.raises(ConfigurationError, match=name):
            ServerSettings.from_env(environment)


def test_valid_production_environment_is_normalized() -> None:
    settings = ServerSettings.from_env(PRODUCTION_ENV)

    assert settings.environment is RuntimeEnvironment.PRODUCTION
    assert settings.database_url == PRODUCTION_ENV["DATABASE_URL"]
    assert settings.allowed_frontend_origins == ("https://crickops.example",)
    assert settings.live_services_enabled is True


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DATABASE_URL", "mysql://db.example/crickops"),
        ("CRICKOPS_COOKIE_SECRET", "too-short"),
        ("CRICKOPS_ENCRYPTION_SECRET", "also-too-short"),
        ("CRICKOPS_ALLOWED_FRONTEND_ORIGINS", "http://crickops.example"),
    ],
)
def test_production_rejects_malformed_values(name: str, value: str) -> None:
    with pytest.raises(ConfigurationError, match=name):
        ServerSettings.from_env(PRODUCTION_ENV | {name: value})


@pytest.mark.parametrize("environment", [{}, {"CRICKOPS_ENV": "staging"}])
def test_missing_or_unknown_runtime_environment_is_rejected(
    environment: dict[str, str],
) -> None:
    with pytest.raises(ConfigurationError, match="CRICKOPS_ENV"):
        ServerSettings.from_env(environment)


@pytest.mark.parametrize("name", ["CRICKOPS_UNDOCUMENTED", "CRICKOPS_OPENAI_API_KEY"])
def test_unknown_crickops_variables_are_rejected(name: str) -> None:
    with pytest.raises(ConfigurationError, match=name):
        ServerSettings.from_env({"CRICKOPS_ENV": "test", name: "unexpected"})


def test_test_mode_disables_live_services_without_secrets() -> None:
    settings = ServerSettings.from_env({"CRICKOPS_ENV": "test"})

    assert settings.environment is RuntimeEnvironment.TEST
    assert settings.live_services_enabled is False
    assert settings.database_url is None
    assert settings.openai_api_key is None


def test_local_live_service_opt_in_requires_server_values() -> None:
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        ServerSettings.from_env(
            {
                "CRICKOPS_ENV": "local",
                "CRICKOPS_LIVE_SERVICES_ENABLED": "true",
            }
        )


def test_boolean_values_are_strict() -> None:
    with pytest.raises(ConfigurationError, match="CRICKOPS_LIVE_SERVICES_ENABLED"):
        ServerSettings.from_env(
            {
                "CRICKOPS_ENV": "local",
                "CRICKOPS_LIVE_SERVICES_ENABLED": "sometimes",
            }
        )
