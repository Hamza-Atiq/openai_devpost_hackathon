from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient


def _client() -> TestClient:
    client = TestClient(create_app(), base_url="https://testserver")
    client.post("/api/v1/workspaces", json={"sample_id": "global-community-cup"})
    return client


def test_custom_profile_requires_priorities_and_returns_validated_fourth_option() -> None:
    client = _client()
    missing = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "custom-missing"},
        json={
            "profiles": ["balanced", "weather_first", "fairness_first", "custom"]
        },
    )
    accepted = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "custom-valid"},
        json={
            "profiles": ["balanced", "weather_first", "fairness_first", "custom"],
            "custom_priorities": {
                "weather_coverage": 45,
                "rest": 30,
                "venue_balance": 10,
                "slot_balance": 5,
                "organizer_preferences": 5,
                "audience_timing": 5,
            },
        },
    )
    run = client.get(f"/api/v1/schedule-runs/{accepted.json()['run_id']}")

    assert missing.status_code == 422
    assert missing.json()["code"] == "custom_priorities_required"
    assert accepted.status_code == 202
    assert len(run.json()["options"]) == 4
    custom = next(item for item in run.json()["options"] if item["profile"] == "custom")
    assert custom["validation_valid"] is True
