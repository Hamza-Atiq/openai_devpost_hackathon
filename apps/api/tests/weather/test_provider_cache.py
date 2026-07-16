from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
from app.weather.cache import WeatherCache, WeatherDataState, build_weather_cache_key
from app.weather.provider import OpenMeteoWeatherProvider

FETCHED_AT = datetime(2026, 7, 16, 12, tzinfo=UTC)


def _payload() -> dict[str, object]:
    return {
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
    }


def test_provider_requests_coordinate_timezone_variables_and_window() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["latitude"] == "31.52"
        assert request.url.params["longitude"] == "74.35"
        assert request.url.params["timezone"] == "Asia/Karachi"
        assert request.url.params["start_date"] == "2026-09-01"
        assert request.url.params["end_date"] == "2026-09-16"
        assert "precipitation_probability" in request.url.params["hourly"]
        return httpx.Response(200, json=_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = OpenMeteoWeatherProvider(client).fetch(
            latitude=31.52,
            longitude=74.35,
            iana_time_zone="Asia/Karachi",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 16),
            fetched_at=FETCHED_AT,
        )

    assert len(result.hours) == 1
    assert result.provider == "open-meteo"


def test_cache_labels_fresh_stale_expired_and_uses_rounded_coordinate_key() -> None:
    key = build_weather_cache_key(
        latitude=31.520401,
        longitude=74.358701,
        iana_time_zone="Asia/Karachi",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 16),
    )
    same_key = build_weather_cache_key(
        latitude=31.520399,
        longitude=74.358699,
        iana_time_zone="Asia/Karachi",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 16),
    )
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=_payload()))
    with httpx.Client(transport=transport) as client:
        forecast = OpenMeteoWeatherProvider(client).fetch(
            latitude=31.52,
            longitude=74.35,
            iana_time_zone="Asia/Karachi",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 16),
            fetched_at=FETCHED_AT,
        )
    cache = WeatherCache()
    cache.put(key, forecast)

    assert key == same_key
    assert cache.read(key, now=FETCHED_AT + timedelta(minutes=29)).state is WeatherDataState.FRESH
    assert cache.read(key, now=FETCHED_AT + timedelta(hours=5)).state is WeatherDataState.STALE
    expired = cache.read(key, now=FETCHED_AT + timedelta(hours=7))
    assert expired.state is WeatherDataState.UNAVAILABLE
    assert expired.forecast is None


def test_cache_miss_is_unavailable_not_safe() -> None:
    result = WeatherCache().read("missing", now=FETCHED_AT)

    assert result.state is WeatherDataState.UNAVAILABLE
    assert result.forecast is None
