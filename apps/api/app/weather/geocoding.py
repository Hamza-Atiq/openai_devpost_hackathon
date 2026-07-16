from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from pydantic import Field, field_validator

from app.domain.common import UUID7, DomainModel
from app.domain.venues import Venue

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class GeocodingCandidate(DomainModel):
    reference_id: str = Field(min_length=1, max_length=240)
    locality_name: str = Field(min_length=1, max_length=120)
    administrative_region: str | None = Field(default=None, max_length=120)
    country_name: str | None = Field(default=None, max_length=120)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    iana_time_zone: str
    provider: str = Field(min_length=1, max_length=80)

    @field_validator("iana_time_zone")
    @classmethod
    def validate_iana_time_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("candidate must include a valid IANA timezone") from error
        return value


class OpenMeteoGeocoder:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def _get_json(self, url: str, params: dict[str, object]) -> dict[str, object]:
        try:
            response = self._client.get(url, params=params, timeout=5.0)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError("geocoding provider unavailable") from error
        if not isinstance(payload, dict):
            raise RuntimeError("geocoding provider returned an invalid response")
        return payload

    def search(
        self,
        search_text: str,
        *,
        country_code: str | None = None,
        limit: int = 5,
    ) -> tuple[GeocodingCandidate, ...]:
        normalized_search = search_text.strip()
        if len(normalized_search) < 2:
            raise ValueError("location search must contain at least two characters")
        if not 1 <= limit <= 10:
            raise ValueError("candidate limit must be between 1 and 10")
        params: dict[str, object] = {
            "name": normalized_search,
            "count": limit,
            "language": "en",
            "format": "json",
        }
        if country_code is not None:
            normalized_country = country_code.upper()
            if len(normalized_country) != 2:
                raise ValueError("country code must contain two letters")
            params["countryCode"] = normalized_country
        payload = self._get_json(GEOCODING_URL, params)
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise RuntimeError("geocoding provider returned an invalid response")
        candidates = tuple(self._candidate(item) for item in results[:limit])
        return candidates

    def resolve_manual_coordinates(
        self,
        *,
        latitude: float,
        longitude: float,
        city: str,
        country_code: str,
    ) -> GeocodingCandidate:
        payload = self._get_json(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": "auto",
                "forecast_days": 1,
            },
        )
        timezone = payload.get("timezone")
        if not isinstance(timezone, str):
            raise RuntimeError("provider did not resolve a timezone for coordinates")
        return GeocodingCandidate(
            reference_id=f"manual:{latitude:.5f},{longitude:.5f}",
            locality_name=city,
            country_code=country_code.upper(),
            latitude=latitude,
            longitude=longitude,
            iana_time_zone=timezone,
            provider="manual-open-meteo-timezone",
        )

    @staticmethod
    def _candidate(raw: object) -> GeocodingCandidate:
        if not isinstance(raw, dict):
            raise RuntimeError("geocoding provider returned an invalid candidate")
        try:
            return GeocodingCandidate(
                reference_id=str(raw["id"]),
                locality_name=raw["name"],
                administrative_region=raw.get("admin1"),
                country_name=raw.get("country"),
                country_code=str(raw["country_code"]).upper(),
                latitude=raw["latitude"],
                longitude=raw["longitude"],
                iana_time_zone=raw["timezone"],
                provider="open-meteo-geocoding",
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("geocoding provider returned an invalid candidate") from error


def confirm_venue(
    *,
    venue_id: UUID7,
    display_name: str,
    candidate: GeocodingCandidate,
    confirmed_at: datetime,
    shared_iana_time_zone: str | None = None,
) -> Venue:
    if shared_iana_time_zone is not None and candidate.iana_time_zone != shared_iana_time_zone:
        raise ValueError("both Version 1 venues must use the same IANA timezone")
    return Venue(
        id=venue_id,
        display_name=display_name,
        city=candidate.locality_name,
        country_code=candidate.country_code,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        iana_time_zone=candidate.iana_time_zone,
        geocoding_provider=candidate.provider,
        geocoding_reference=candidate.reference_id,
        confirmed_at=confirmed_at,
    )
