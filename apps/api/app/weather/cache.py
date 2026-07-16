from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from enum import StrEnum

from app.domain.common import DomainModel
from app.weather.normalize import NormalizedForecast
from app.weather.provider import HOURLY_VARIABLES


class WeatherDataState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class CachedWeather(DomainModel):
    state: WeatherDataState
    forecast: NormalizedForecast | None = None


def build_weather_cache_key(
    *,
    latitude: float,
    longitude: float,
    iana_time_zone: str,
    start_date: date,
    end_date: date,
    provider_model_version: str = "best-match/v1",
) -> str:
    payload = {
        "latitude": round(latitude, 4),
        "longitude": round(longitude, 4),
        "time_zone": iana_time_zone,
        "variables": HOURLY_VARIABLES,
        "window": (start_date.isoformat(), end_date.isoformat()),
        "provider_model_version": provider_model_version,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class WeatherCache:
    def __init__(self) -> None:
        self._values: dict[str, NormalizedForecast] = {}

    def put(self, key: str, forecast: NormalizedForecast) -> None:
        self._values[key] = forecast

    def read(self, key: str, *, now: datetime) -> CachedWeather:
        forecast = self._values.get(key)
        if forecast is None:
            return CachedWeather(state=WeatherDataState.UNAVAILABLE)
        age = max(now - forecast.fetched_at, timedelta())
        if age <= timedelta(minutes=30):
            return CachedWeather(state=WeatherDataState.FRESH, forecast=forecast)
        if age <= timedelta(hours=6):
            return CachedWeather(state=WeatherDataState.STALE, forecast=forecast)
        return CachedWeather(state=WeatherDataState.UNAVAILABLE)
