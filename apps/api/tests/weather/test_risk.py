from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.weather.normalize import NormalizedWeatherHour
from app.weather.risk import calculate_fixture_risk, summarize_schedule_weather

START = datetime(2026, 9, 1, 9, tzinfo=UTC)


def _hour(**overrides: object) -> NormalizedWeatherHour:
    values: dict[str, object] = {
        "starts_at_utc": START,
        "precipitation_probability": 80,
        "precipitation_mm": 2,
        "temperature_c": 36,
        "apparent_temperature_c": 38,
        "wind_speed_kmh": 40,
        "wind_gust_kmh": 50,
        "weather_code": 95,
    }
    values.update(overrides)
    return NormalizedWeatherHour.model_validate(values)


def test_golden_hourly_vector_matches_spec_formula() -> None:
    result = calculate_fixture_risk(
        (_hour(),),
        fixture_starts_at_utc=START + timedelta(minutes=30),
        allocation_minutes=240,
    )

    assert result.covered is True
    assert result.risk == 78
    assert result.components.rain == 80
    assert round(result.components.heat, 1) == 46.2
    assert round(result.components.wind, 1) == 42.9
    assert result.components.condition == 90
    assert result.quality == "complete"


def test_incomplete_core_data_remains_unknown_not_zero() -> None:
    result = calculate_fixture_risk(
        (_hour(precipitation_probability=None),),
        fixture_starts_at_utc=START,
        allocation_minutes=120,
    )

    assert result.covered is False
    assert result.risk is None
    assert result.quality == "incomplete"


def test_schedule_coverage_is_separate_for_21_day_window_beyond_16_day_forecast() -> None:
    known = calculate_fixture_risk((_hour(),), fixture_starts_at_utc=START, allocation_minutes=240)
    unknown = calculate_fixture_risk(
        (),
        fixture_starts_at_utc=START + timedelta(days=20),
        allocation_minutes=240,
    )

    summary = summarize_schedule_weather((known,) * 12 + (unknown,) * 3)

    assert summary.weather_coverage == 80.0
    assert summary.weather_risk == 78.0
    assert summary.uncovered_fixture_count == 3
    assert summary.coverage_warning is True
