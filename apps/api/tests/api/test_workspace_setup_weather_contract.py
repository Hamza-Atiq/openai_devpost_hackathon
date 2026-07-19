from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient

EXPECTED_PATHS = {
    "/api/v1/workspaces",
    "/api/v1/workspace",
    "/api/v1/workspace/reset",
    "/api/v1/workspace/export",
    "/api/v1/samples",
    "/api/v1/tournament",
    "/api/v1/locations/search",
    "/api/v1/venues/{venue_id}/confirm-location",
    "/api/v1/tournament/interpret",
    "/api/v1/constraints/propose",
    "/api/v1/constraints/confirm",
    "/api/v1/constraints/reject",
    "/api/v1/tournament/precheck",
    "/api/v1/weather/refresh",
    "/api/v1/weather",
    "/api/v1/weather/demo-scenarios/{scenario_id}/activate",
    "/api/v1/weather/thresholds",
}


def api_client(app=None) -> TestClient:
    return TestClient(app or create_app(), base_url="https://testserver")


def test_openapi_exposes_versioned_workspace_setup_and_weather_routes() -> None:
    document = create_app().openapi()

    assert EXPECTED_PATHS.issubset(document["paths"])


def test_samples_include_global_and_pakistan_tournaments() -> None:
    client = api_client()

    response = client.get("/api/v1/samples")

    assert response.status_code == 200
    assert {item["sample_id"] for item in response.json()} == {
        "global-community-cup",
        "pakistan-community-cup",
    }


def test_guest_workspace_cookie_restores_only_its_sample() -> None:
    app = create_app()
    global_guest = api_client(app)
    pakistan_guest = api_client(app)

    created = global_guest.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    )
    pakistan_guest.post(
        "/api/v1/workspaces",
        json={"sample_id": "pakistan-community-cup"},
    )
    restored = global_guest.get("/api/v1/workspace")

    assert created.status_code == 201
    assert "__Host-crickops_guest=" in created.headers["set-cookie"]
    assert "Secure" in created.headers["set-cookie"]
    assert "HttpOnly" in created.headers["set-cookie"]
    assert restored.json()["tournament"]["name"] == "Global Community Cricket Cup"
    assert restored.json() != pakistan_guest.get("/api/v1/workspace").json()
    assert restored.headers["cache-control"] == "private, no-store, max-age=0"
    assert restored.headers["vary"] == "Cookie"


def test_missing_workspace_uses_problem_details() -> None:
    response = api_client().get("/api/v1/workspace")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "workspace_auth_required"
    assert response.json()["retryable"] is False
    assert response.json()["correlation_id"]


def test_invalid_sample_uses_problem_details() -> None:
    response = api_client().post(
        "/api/v1/workspaces",
        json={"sample_id": "not-a-sample"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_sample"


def test_tournament_update_rejects_unsupported_format_as_problem_details() -> None:
    client = api_client()
    created = client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    ).json()
    tournament = created["tournament"]
    tournament["match_format_preset"] = "ODI"

    response = client.put("/api/v1/tournament", json=tournament)

    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_failed"
    assert any(
        error["location"][-1] == "match_format_preset"
        for error in response.json()["field_errors"]
    )


def test_constraint_confirmation_persists_ready_state_and_rejects_stale_revision() -> None:
    client = api_client()
    created = client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    ).json()
    revision = created["tournament"]["revision"]

    confirmed = client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": revision,
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )
    restored = client.get("/api/v1/workspace")
    stale = client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": revision,
            "selection": {"match_format_preset": "T10", "allocation_minutes": 120},
        },
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "ready_to_schedule"
    assert restored.json()["constraint_confirmation"]["selection"]["match_format_preset"] == "T20"
    assert restored.json()["tournament"]["status"] == "ready_to_schedule"
    assert restored.json()["tournament"]["revision"] == revision + 1
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_tournament_revision"


def test_deterministic_weather_activation_survives_live_unavailability() -> None:
    client = api_client()
    client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    )

    unavailable = client.post("/api/v1/weather/refresh", json={"mode": "live"})
    activated = client.post(
        "/api/v1/weather/demo-scenarios/rain-threshold-v1/activate",
        json={"confirmation": True},
    )
    weather = client.get("/api/v1/weather")

    assert unavailable.status_code == 200
    assert unavailable.json()["quality"] == "unavailable"
    assert unavailable.json()["demo_mode_available"] is True
    assert activated.status_code == 200
    assert activated.json()["mode"] == "deterministic"
    assert weather.json()["scenario_id"] == "rain-threshold-v1"


def test_weather_threshold_stays_proposed_until_explicit_confirmation() -> None:
    client = TestClient(create_app(), base_url="https://testserver")
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "global-community-cup"}
    ).json()
    revision = created["tournament"]["revision"]
    client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": revision,
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )
    proposal = client.post(
        "/api/v1/weather/thresholds",
        json={"metric": "precipitation_probability", "value": 70},
    )
    before = client.get("/api/v1/workspace").json()

    assert proposal.status_code == 200
    assert proposal.json()["status"] == "proposed"
    assert "weather_threshold" not in before["constraint_confirmation"]["selection"]

    confirmed = client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": before["tournament"]["revision"],
            "selection": {
                "weather_threshold": {
                    "metric": "precipitation_probability",
                    "value": 70,
                }
            },
        },
    )
    after = client.get("/api/v1/workspace").json()

    assert confirmed.status_code == 200
    assert after["constraint_confirmation"]["selection"]["match_format_preset"] == "T20"
    assert after["constraint_confirmation"]["selection"]["weather_threshold"]["value"] == 70
