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


def test_blank_workspace_starts_with_an_editable_version_one_skeleton() -> None:
    client = api_client()

    created = client.post("/api/v1/workspaces", json={"sample_id": None})
    setup = client.get("/api/v1/tournament")

    assert created.status_code == 201
    assert created.json()["tournament"] is not None
    assert setup.status_code == 200
    tournament = setup.json()
    assert tournament["name"] == "Untitled Cricket Tournament"
    assert len(tournament["teams"]) == 8
    assert len(tournament["groups"]) == 2
    assert {len(group["team_ids"]) for group in tournament["groups"]} == {4}
    assert len(tournament["venues"]) == 2
    assert tournament["status"] == "draft_setup"


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


class StubWeatherService:
    def __init__(self) -> None:
        self.modes: list[str] = []

    def refresh(self, tournament, *, mode: str, scenario_id: str | None = None):
        self.modes.append(mode)
        risks = {str(slot.id): float(index) for index, slot in enumerate(tournament.slots)}
        return {
            "mode": mode,
            "quality": "complete",
            "demo_mode_available": True,
            "scenario_id": scenario_id,
            "provider": "open-meteo" if mode == "live" else "deterministic-demo",
            "fetched_at": "2026-07-19T12:00:00Z",
            "issued_at": "2026-07-19T11:45:00Z",
            "coverage": 100.0,
            "slot_risks": risks,
            "slot_details": {
                slot_id: {
                    "risk": risk,
                    "covered": True,
                    "quality": "complete",
                    "components": {"rain": risk},
                }
                for slot_id, risk in risks.items()
            },
            "attribution": "Weather data by Open-Meteo.com",
            "guidance": "Weather risk is planning guidance only.",
        }


def test_sample_workspace_starts_with_real_deterministic_weather_snapshot() -> None:
    service = StubWeatherService()
    app = create_app(weather_service=service)
    persisted_tokens: list[str | None] = []
    app.state.workspace_store.persist = persisted_tokens.append
    client = api_client(app)

    created = client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    )

    assert created.status_code == 201
    assert created.json()["weather"]["mode"] == "deterministic"
    assert created.json()["weather"]["coverage"] == 100.0
    assert service.modes == ["deterministic"]
    assert len(persisted_tokens) == 1


def test_reset_demo_clears_tournament_owned_state_and_loads_the_selected_sample() -> None:
    service = StubWeatherService()
    app = create_app(weather_service=service)
    client = api_client(app)
    client.post("/api/v1/workspaces", json={"sample_id": "pakistan-community-cup"})
    token = client.cookies.get("__Host-crickops_guest")
    workspace = app.state.workspace_store.get(token)
    assert workspace is not None
    workspace.schedule_runs["old-run"] = {"status": "complete"}
    workspace.official_versions.append({"version_id": "old-version"})
    workspace.disruptions["old-disruption"] = {"status": "active"}
    app.state.operations.audit_events[workspace.workspace_id] = [{"event_id": "old-event"}]

    reset = client.post(
        "/api/v1/workspace/reset",
        json={"sample_id": "global-community-cup"},
    )
    restored = client.get("/api/v1/workspace")

    assert reset.status_code == 200
    assert restored.json()["tournament"]["name"] == "Global Community Cricket Cup"
    assert workspace.schedule_runs == {}
    assert workspace.official_versions == []
    assert workspace.disruptions == {}
    assert restored.json()["weather"]["mode"] == "deterministic"
    reset_event = app.state.operations.audit_events[workspace.workspace_id][0]
    assert reset_event["event_type"] == "workspace_reset"


def test_live_weather_service_persists_slot_level_risk_and_provenance() -> None:
    service = StubWeatherService()
    client = api_client(create_app(weather_service=service))
    client.post("/api/v1/workspaces", json={"sample_id": "global-community-cup"})

    response = client.post("/api/v1/weather/refresh", json={"mode": "live"})
    restored = client.get("/api/v1/weather")

    assert response.status_code == 200
    assert response.json()["quality"] == "complete"
    assert response.json()["coverage"] == 100.0
    assert len(response.json()["slot_risks"]) == 28
    assert response.json()["provider"] == "open-meteo"
    assert response.json()["attribution"] == "Weather data by Open-Meteo.com"
    assert restored.json() == response.json()
    assert service.modes == ["deterministic", "live"]


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
