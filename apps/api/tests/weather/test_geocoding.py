from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from app.weather.geocoding import OpenMeteoGeocoder, confirm_venue
from tests.domain.factories import uuid7

CONFIRMED_AT = datetime(2026, 7, 16, 12, tzinfo=UTC)


def test_search_returns_bounded_candidates_and_keeps_venue_name_separate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["name"] == "Lahore, Punjab, 54000"
        assert request.url.params["countryCode"] == "PK"
        assert request.url.params["count"] == "2"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": index,
                        "name": f"Lahore {index}",
                        "admin1": "Punjab",
                        "country": "Pakistan",
                        "country_code": "PK",
                        "latitude": 31.52 + index / 100,
                        "longitude": 74.35,
                        "timezone": "Asia/Karachi",
                    }
                    for index in range(1, 5)
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        candidates = OpenMeteoGeocoder(client).search(
            "Lahore, Punjab, 54000", country_code="PK", limit=2
        )

    assert len(candidates) == 2
    assert candidates[0].locality_name == "Lahore 1"
    assert candidates[0].iana_time_zone == "Asia/Karachi"
    assert not hasattr(candidates[0], "venue_name")


def test_search_with_no_results_returns_empty_candidates() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
    with httpx.Client(transport=transport) as client:
        candidates = OpenMeteoGeocoder(client).search("No Such Place")

    assert candidates == ()


def test_manual_coordinates_resolve_timezone_before_confirmation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["latitude"] == "31.5204"
        assert request.url.params["longitude"] == "74.3587"
        assert request.url.params["timezone"] == "auto"
        return httpx.Response(200, json={"timezone": "Asia/Karachi"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        candidate = OpenMeteoGeocoder(client).resolve_manual_coordinates(
            latitude=31.5204,
            longitude=74.3587,
            city="Lahore",
            country_code="PK",
        )

    venue = confirm_venue(
        venue_id=uuid7(700),
        display_name="National Cricket Ground",
        candidate=candidate,
        confirmed_at=CONFIRMED_AT,
    )

    assert venue.display_name == "National Cricket Ground"
    assert venue.geocoding_provider == "manual-open-meteo-timezone"
    assert venue.iana_time_zone == "Asia/Karachi"


def test_confirmation_rejects_cross_timezone_second_venue() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"timezone": "Asia/Dhaka"})
    )
    with httpx.Client(transport=transport) as client:
        candidate = OpenMeteoGeocoder(client).resolve_manual_coordinates(
            latitude=23.81,
            longitude=90.41,
            city="Dhaka",
            country_code="BD",
        )

    with pytest.raises(ValueError, match="same IANA timezone"):
        confirm_venue(
            venue_id=uuid7(701),
            display_name="Second Ground",
            candidate=candidate,
            confirmed_at=CONFIRMED_AT,
            shared_iana_time_zone="Asia/Karachi",
        )


def test_provider_failure_is_explicit() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="geocoding provider unavailable"):
            OpenMeteoGeocoder(client).search("Lahore")
