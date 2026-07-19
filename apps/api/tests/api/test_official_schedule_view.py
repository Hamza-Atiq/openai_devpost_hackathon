from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient


def _client() -> TestClient:
    client = TestClient(create_app(), base_url="https://testserver")
    client.post("/api/v1/workspaces", json={"sample_id": "global-community-cup"})
    return client


def test_official_schedule_is_empty_until_explicit_approval() -> None:
    response = _client().get("/api/v1/official-schedule")

    assert response.status_code == 200
    assert response.json() == {"official": None}


def test_official_schedule_returns_backend_owned_validated_fixture_views() -> None:
    client = _client()
    tournament = client.get("/api/v1/tournament").json()
    client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": tournament["revision"],
            "selection": {
                "match_format_preset": tournament["match_format_preset"],
                "allocation_minutes": tournament["allocation_minutes"],
            },
        },
    )
    accepted = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "official-view-generation"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()
    run = client.get(f"/api/v1/schedule-runs/{accepted['run_id']}").json()
    draft_id = run["draft_ids"][0]
    client.post(
        f"/api/v1/schedule-drafts/{draft_id}/approve",
        headers={"Idempotency-Key": "official-view-approval"},
        json={"confirmation": True},
    )

    response = client.get("/api/v1/official-schedule")
    official = response.json()["official"]

    assert response.status_code == 200
    assert official["version_number"] == 1
    assert official["approved_draft_id"] == draft_id
    assert official["validation_valid"] is True
    assert len(official["fixtures"]) == 15
    assert [fixture["code"] for fixture in official["fixtures"]] == [
        *(f"G{number:02d}" for number in range(1, 13)),
        "SF1",
        "SF2",
        "F1",
    ]
    assert all(fixture["validation"] == "valid" for fixture in official["fixtures"])
    assert all(fixture["slot_id"] for fixture in official["fixtures"])
    assert all("timezone" in fixture for fixture in official["fixtures"])
    assert all("+" in fixture["starts_at"] for fixture in official["fixtures"])
    assert official["fixtures"][12]["home"] == "Group A Winner"
    assert official["fixtures"][14]["home"] == "Semifinal 1 Winner"
    group_names = {
        fixture["home"] for fixture in official["fixtures"][:12]
    } | {fixture["away"] for fixture in official["fixtures"][:12]}
    assert not any(len(name) == 36 and name.count("-") == 4 for name in group_names)
