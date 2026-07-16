from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from app.domain.common import UUID7, DomainModel, UtcDateTime


class WeatherMode(StrEnum):
    LIVE = "live"
    DETERMINISTIC = "deterministic"


class WeatherQuality(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class WeatherHour(DomainModel):
    starts_at_utc: UtcDateTime
    precipitation_probability: float | None = None
    temperature_c: float | None = None
    wind_speed_kph: float | None = None


class WeatherSnapshot(DomainModel):
    venue_id: UUID7
    mode: WeatherMode
    issued_at: UtcDateTime
    fetched_at: UtcDateTime
    valid_hours: tuple[WeatherHour, ...]
    quality: WeatherQuality
    provider_metadata: Mapping[str, object]
