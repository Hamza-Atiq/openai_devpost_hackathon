from __future__ import annotations

from datetime import date
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from app.domain.common import UUID7, DomainModel, UtcDateTime


class SlotAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class SlotSource(StrEnum):
    ORGANIZER = "organizer"
    BLACKOUT = "blackout"
    DISRUPTION = "disruption"


class Venue(DomainModel):
    id: UUID7
    display_name: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=120)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    iana_time_zone: str
    geocoding_provider: str = Field(min_length=1, max_length=80)
    geocoding_reference: str | None = Field(default=None, max_length=240)
    confirmed_at: UtcDateTime

    @field_validator("iana_time_zone")
    @classmethod
    def validate_iana_time_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("iana_time_zone must be a valid IANA timezone") from error
        return value


class VenueSlot(DomainModel):
    id: UUID7
    venue_id: UUID7
    starts_at_utc: UtcDateTime
    ends_at_utc: UtcDateTime
    local_date: date
    availability: SlotAvailability
    source: SlotSource

    @model_validator(mode="after")
    def validate_interval(self) -> VenueSlot:
        if self.ends_at_utc <= self.starts_at_utc:
            raise ValueError("ends_at_utc must be after starts_at_utc")
        return self
