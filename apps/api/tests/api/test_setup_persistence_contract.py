from __future__ import annotations

from datetime import date, datetime, timedelta

from app.main import create_app
from fastapi.testclient import TestClient


def api_client() -> TestClient:
    return TestClient(create_app(), base_url="https://testserver")


def pakistan_setup_payload(revision: int) -> dict[str, object]:
    return {
        "expected_revision": revision,
        "match_format_preset": "T10",
        "start_date": "2026-08-10",
        "end_date": "2026-08-30",
        "venues": [
            {
                "display_name": "Rawalpindi Cricket Stadium",
                "city": "Rawalpindi",
                "country_code": "PK",
                "latitude": 33.65199,
                "longitude": 73.07716,
                "iana_time_zone": "Asia/Karachi",
            },
            {
                "display_name": "Lahore Cricket Stadium",
                "city": "Lahore",
                "country_code": "PK",
                "latitude": 31.5134,
                "longitude": 74.3335,
                "iana_time_zone": "Asia/Karachi",
            },
        ],
        "weekday_start_times": ["19:00"],
        "weekend_start_times": ["17:00", "19:00"],
        "blackout_dates": ["2026-08-18"],
        "minimum_rest_minutes": 1_440,
        "priorities": {
            "minimize_weather_risk": True,
            "maximize_fair_rest": True,
            "balance_venue_allocation": True,
            "prefer_selected_time_slots": True,
            "minimize_schedule_changes": True,
        },
    }


def test_pakistan_sample_exposes_its_authoritative_setup_values() -> None:
    client = api_client()
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "pakistan-community-cup"}
    )

    setup = client.get("/api/v1/tournament")

    assert created.status_code == 201
    assert setup.status_code == 200
    assert setup.json()["name"] == "Pakistan Community Cricket Cup"
    assert setup.json()["match_format_preset"] == "T20"
    assert [venue["display_name"] for venue in setup.json()["venues"]] == [
        "Canal Community Ground",
        "Garden Sports Ground",
    ]
    start_date = date.fromisoformat(setup.json()["start_date"])
    end_date = date.fromisoformat(setup.json()["end_date"])
    assert date.today() + timedelta(days=2) <= start_date <= date.today() + timedelta(days=4)
    assert end_date - start_date == timedelta(days=9)


def test_complete_setup_edit_is_normalized_persisted_and_restored() -> None:
    client = api_client()
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "pakistan-community-cup"}
    ).json()
    revision = created["tournament"]["revision"]

    saved = client.put(
        "/api/v1/tournament",
        json=pakistan_setup_payload(revision),
        headers={"Idempotency-Key": "setup-edit-001"},
    )
    restored = client.get("/api/v1/tournament")

    assert saved.status_code == 200, saved.text
    assert restored.status_code == 200
    assert saved.json() == restored.json()
    assert restored.json()["revision"] == revision + 1
    assert restored.json()["status"] == "awaiting_constraint_confirmation"
    assert restored.json()["match_format_preset"] == "T10"
    assert restored.json()["allocation_minutes"] == 120
    assert restored.json()["start_date"] == "2026-08-10"
    assert restored.json()["end_date"] == "2026-08-30"
    assert [venue["display_name"] for venue in restored.json()["venues"]] == [
        "Rawalpindi Cricket Stadium",
        "Lahore Cricket Stadium",
    ]
    assert {venue["iana_time_zone"] for venue in restored.json()["venues"]} == {
        "Asia/Karachi"
    }

    slots = restored.json()["slots"]
    assert len(slots) == 54
    assert sum(slot["availability"] == "unavailable" for slot in slots) == 2
    assert {slot["source"] for slot in slots if slot["availability"] == "unavailable"} == {
        "blackout"
    }
    assert all(
        (
            datetime.fromisoformat(slot["ends_at_utc"])
            - datetime.fromisoformat(slot["starts_at_utc"])
        ).total_seconds()
        == 120 * 60
        for slot in slots
    )
    assert restored.json()["constraints"]["confirmation_state"] == "draft"


def test_setup_edit_rejects_stale_revision_without_overwriting_saved_state() -> None:
    client = api_client()
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "pakistan-community-cup"}
    ).json()
    revision = created["tournament"]["revision"]
    first_payload = pakistan_setup_payload(revision)
    assert (
        client.put(
            "/api/v1/tournament",
            json=first_payload,
            headers={"Idempotency-Key": "setup-edit-first"},
        ).status_code
        == 200
    )

    stale_payload = pakistan_setup_payload(revision)
    stale_payload["start_date"] = "2026-08-11"
    stale = client.put(
        "/api/v1/tournament",
        json=stale_payload,
        headers={"Idempotency-Key": "setup-edit-stale"},
    )
    restored = client.get("/api/v1/tournament")

    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_tournament_revision"
    assert restored.json()["start_date"] == "2026-08-10"


def test_setup_edit_rejects_more_than_twenty_one_calendar_days() -> None:
    client = api_client()
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "pakistan-community-cup"}
    ).json()
    payload = pakistan_setup_payload(created["tournament"]["revision"])
    payload["end_date"] = "2026-08-31"

    response = client.put(
        "/api/v1/tournament",
        json=payload,
        headers={"Idempotency-Key": "setup-edit-too-long"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_tournament_window"
    assert "21 calendar days" in response.json()["detail"]
