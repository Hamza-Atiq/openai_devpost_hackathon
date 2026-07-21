from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient

PROFILES = ["balanced", "weather_first", "fairness_first"]


def api_client() -> TestClient:
    return TestClient(create_app(), base_url="https://testserver")


def confirm(client: TestClient, revision: int) -> int:
    response = client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": revision,
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["revision"]


def insufficient_capacity_payload(revision: int) -> dict[str, object]:
    return {
        "expected_revision": revision,
        "match_format_preset": "T20",
        "start_date": "2026-09-01",
        "end_date": "2026-09-07",
        "venues": [
            {
                "display_name": "Canal Community Ground",
                "city": "Lahore",
                "country_code": "PK",
                "latitude": 31.5204,
                "longitude": 74.3587,
                "iana_time_zone": "Asia/Karachi",
            },
            {
                "display_name": "Garden Sports Ground",
                "city": "Lahore",
                "country_code": "PK",
                "latitude": 31.5,
                "longitude": 74.32,
                "iana_time_zone": "Asia/Karachi",
            },
        ],
        "weekday_start_times": ["10:00"],
        "weekend_start_times": ["10:00"],
        "blackout_dates": [],
        "minimum_rest_minutes": 0,
        "priorities": {},
    }


def test_generation_refuses_an_unconfirmed_setup_revision() -> None:
    client = api_client()
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "pakistan-community-cup"}
    ).json()

    response = client.post(
        "/api/v1/schedule-runs",
        json={"profiles": PROFILES, "expected_revision": created["tournament"]["revision"]},
        headers={"Idempotency-Key": "unconfirmed-generation"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "constraints_not_confirmed"


def test_precheck_uses_deterministic_capacity_evidence_after_confirmation() -> None:
    client = api_client()
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "pakistan-community-cup"}
    ).json()
    saved = client.put(
        "/api/v1/tournament",
        json=insufficient_capacity_payload(created["tournament"]["revision"]),
        headers={"Idempotency-Key": "insufficient-setup"},
    ).json()
    confirmed_revision = confirm(client, saved["revision"])

    precheck = client.post(
        "/api/v1/tournament/precheck",
        json={"expected_revision": confirmed_revision},
    )
    generated = client.post(
        "/api/v1/schedule-runs",
        json={"profiles": PROFILES, "expected_revision": confirmed_revision},
        headers={"Idempotency-Key": "insufficient-generation"},
    )

    assert precheck.status_code == 200
    assert precheck.json()["ready"] is False
    assert "insufficient_capacity" in precheck.json()["violations"]
    assert precheck.json()["remedies"][0]["code"] == "add_venue_slots"
    assert generated.status_code == 422
    assert generated.json()["code"] == "schedule_precheck_failed"
    assert "available capacity" in generated.json()["detail"].lower()
    assert generated.json()["evidence"][0]["code"] == "insufficient_capacity"
    assert generated.json()["evidence"][0]["message"]
    assert generated.json()["remedies"][0]["code"] == "add_venue_slots"
    assert generated.json()["remedies"][0]["description"]


def test_precheck_and_generation_reject_stale_revisions() -> None:
    client = api_client()
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "pakistan-community-cup"}
    ).json()
    stale_revision = created["tournament"]["revision"]
    confirmed_revision = confirm(client, stale_revision)

    precheck = client.post(
        "/api/v1/tournament/precheck", json={"expected_revision": stale_revision}
    )
    generated = client.post(
        "/api/v1/schedule-runs",
        json={"profiles": PROFILES, "expected_revision": stale_revision},
        headers={"Idempotency-Key": "stale-generation"},
    )

    assert confirmed_revision == stale_revision + 1
    assert precheck.status_code == 409
    assert precheck.json()["code"] == "stale_tournament_revision"
    assert generated.status_code == 409
    assert generated.json()["code"] == "stale_tournament_revision"


def test_latest_schedule_run_recovers_the_current_workspace_comparison() -> None:
    client = api_client()
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "pakistan-community-cup"}
    ).json()
    confirmed_revision = confirm(client, created["tournament"]["revision"])
    generated = client.post(
        "/api/v1/schedule-runs",
        json={"profiles": PROFILES, "expected_revision": confirmed_revision},
        headers={"Idempotency-Key": "latest-run-generation"},
    )

    latest = client.get("/api/v1/schedule-runs/latest")

    assert generated.status_code == 202
    assert latest.status_code == 200
    assert latest.json()["run_id"] == generated.json()["run_id"]
    assert latest.json()["status"] == "completed"
