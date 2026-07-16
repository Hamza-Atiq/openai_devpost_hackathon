from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.weather.normalize import normalize_open_meteo

FETCHED_AT = datetime(2026, 7, 16, 12, tzinfo=UTC)


def test_open_meteo_hourly_payload_normalizes_local_times_to_utc() -> None:
    result = normalize_open_meteo(
        {
            "latitude": 31.52,
            "longitude": 74.35,
            "timezone": "Asia/Karachi",
            "hourly": {
                "time": ["2026-09-01T14:00"],
                "precipitation_probability": [70],
                "precipitation": [1.5],
                "temperature_2m": [34],
                "apparent_temperature": [38],
                "wind_speed_10m": [22],
                "wind_gusts_10m": [35],
                "weather_code": [61],
            },
        },
        fetched_at=FETCHED_AT,
    )

    assert result.hours[0].starts_at_utc == datetime(2026, 9, 1, 9, tzinfo=UTC)
    assert result.hours[0].precipitation_probability == 70
    assert result.attribution.display_text == "Weather data by Open-Meteo.com"
    assert result.fetched_at == FETCHED_AT


def test_misaligned_hourly_arrays_are_rejected() -> None:
    with pytest.raises(ValueError, match="hourly arrays"):
        normalize_open_meteo(
            {
                "latitude": 31.52,
                "longitude": 74.35,
                "timezone": "Asia/Karachi",
                "hourly": {
                    "time": ["2026-09-01T14:00"],
                    "precipitation_probability": [70, 80],
                },
            },
            fetched_at=FETCHED_AT,
        )
