from __future__ import annotations

from decimal import Decimal

import pytest
from app.optimization.config import (
    config_checksum,
    display_round,
    load_optimization_config,
    normalize_custom_priorities,
    solver_coefficient,
)


def test_v1_configuration_matches_approved_profile_defaults() -> None:
    config = load_optimization_config()

    assert config.version == "optimization-config/v1"
    assert config.profiles["balanced"].weights.model_dump(exclude={"schema_version"}) == {
        "weather_coverage": 25,
        "rest": 25,
        "venue_balance": 15,
        "slot_balance": 10,
        "organizer_preferences": 20,
        "audience_timing": 5,
    }
    assert config.profiles["weather-first"].weights.weather_coverage == 50
    assert config.profiles["fairness-first"].weights.rest == 40
    assert all(sum(profile.weights.values()) == 100 for profile in config.profiles.values())
    assert {
        name: profile.missing_coverage_penalty for name, profile in config.profiles.items()
    } == {
        "balanced": 55,
        "weather-first": 70,
        "fairness-first": 45,
    }


def test_weather_slot_and_rounding_boundaries_are_typed() -> None:
    config = load_optimization_config()

    assert config.weather.lead_minutes == 30
    assert config.weather.lag_minutes == 30
    assert config.weather.hard_threshold_suggestions.precipitation_probability == 70
    assert config.weather.hard_threshold_suggestions.thunderstorm_wmo_codes == (95, 96, 99)
    assert config.slot_categories.morning == ("06:00", "11:59")
    assert config.slot_categories.off_hours == ("23:00", "05:59")
    assert config.audience.off_hours_penalty == 30
    assert display_round(Decimal("2.25")) == Decimal("2.3")
    assert solver_coefficient(Decimal("12.25")) == 123


def test_custom_priorities_are_bounded_normalized_and_nonzero() -> None:
    normalized = normalize_custom_priorities({"weather_coverage": 1, "rest": 1, "venue_balance": 2})

    assert normalized == {
        "weather_coverage": Decimal("25"),
        "rest": Decimal("25"),
        "venue_balance": Decimal("50"),
    }
    with pytest.raises(ValueError, match="all-zero"):
        normalize_custom_priorities({"weather_coverage": 0, "rest": 0})
    with pytest.raises(ValueError, match="between 0 and 100"):
        normalize_custom_priorities({"weather_coverage": 101})


def test_v1_configuration_has_reviewed_golden_checksum() -> None:
    assert config_checksum() == "0503e89da095a630754476e55a7aea17cf6ec35c41872fcb96a53cbdd30f1921"
