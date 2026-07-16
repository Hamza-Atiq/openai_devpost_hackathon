from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pydantic import Field

from app.domain.common import DomainModel, UtcDateTime


class WeatherAttribution(DomainModel):
    provider: str = "Open-Meteo"
    display_text: str = "Weather data by Open-Meteo.com"
    provider_url: str = "https://open-meteo.com/"
    license_name: str = "CC BY 4.0"
    license_url: str = "https://creativecommons.org/licenses/by/4.0/"


class NormalizedWeatherHour(DomainModel):
    starts_at_utc: UtcDateTime
    precipitation_probability: float | None = Field(default=None, ge=0, le=100)
    precipitation_mm: float | None = Field(default=None, ge=0)
    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    wind_speed_kmh: float | None = Field(default=None, ge=0)
    wind_gust_kmh: float | None = Field(default=None, ge=0)
    weather_code: int | None = None


class NormalizedForecast(DomainModel):
    provider: str = "open-meteo"
    provider_model_version: str = "best-match/v1"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    iana_time_zone: str
    fetched_at: UtcDateTime
    issued_at: UtcDateTime | None = None
    hours: tuple[NormalizedWeatherHour, ...]
    attribution: WeatherAttribution = WeatherAttribution()


_HOURLY_FIELDS = {
    "precipitation_probability": "precipitation_probability",
    "precipitation": "precipitation_mm",
    "temperature_2m": "temperature_c",
    "apparent_temperature": "apparent_temperature_c",
    "wind_speed_10m": "wind_speed_kmh",
    "wind_gusts_10m": "wind_gust_kmh",
    "weather_code": "weather_code",
}


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, list | tuple):
        raise ValueError(f"{field} must be an hourly array")
    return value


def normalize_open_meteo(
    payload: Mapping[str, object],
    *,
    fetched_at: datetime,
) -> NormalizedForecast:
    hourly = payload.get("hourly")
    if not isinstance(hourly, Mapping):
        raise ValueError("Open-Meteo response must include hourly data")
    times = _sequence(hourly.get("time"), "time")
    arrays: dict[str, Sequence[object]] = {}
    for source_name, target_name in _HOURLY_FIELDS.items():
        raw_values = hourly.get(source_name)
        if raw_values is not None:
            values = _sequence(raw_values, source_name)
            if len(values) != len(times):
                raise ValueError("Open-Meteo hourly arrays must have equal lengths")
            arrays[target_name] = values

    time_zone = str(payload["timezone"])
    zone = ZoneInfo(time_zone)
    normalized_hours = []
    for index, raw_time in enumerate(times):
        local_time = datetime.fromisoformat(str(raw_time)).replace(tzinfo=zone)
        values = {
            target_name: source_values[index] for target_name, source_values in arrays.items()
        }
        normalized_hours.append(
            NormalizedWeatherHour(
                starts_at_utc=local_time.astimezone(UTC),
                **values,
            )
        )
    return NormalizedForecast(
        latitude=payload["latitude"],
        longitude=payload["longitude"],
        iana_time_zone=time_zone,
        fetched_at=fetched_at,
        hours=tuple(normalized_hours),
    )
