from app.main import create_app
from fastapi.testclient import TestClient


class StubWeatherService:
    def refresh(self, tournament, *, mode: str, scenario_id: str | None = None):
        risks = {str(slot.id): 20.0 for slot in tournament.slots}
        return {
            "mode": mode,
            "quality": "complete",
            "scenario_id": scenario_id,
            "coverage": 100.0,
            "slot_risks": risks,
            "slot_details": {},
        }


def test_slot_affecting_tournament_change_invalidates_weather_evidence() -> None:
    client = TestClient(
        create_app(weather_service=StubWeatherService()), base_url="https://testserver"
    )
    client.post("/api/v1/workspaces", json={"sample_id": "global-community-cup"})
    refreshed = client.post("/api/v1/weather/refresh", json={"mode": "live"})
    assert refreshed.json()["coverage"] == 100.0

    changed = client.patch(
        "/api/v1/tournament",
        json={"match_format_preset": "T10", "allocation_minutes": 120},
    )
    weather = client.get("/api/v1/weather")

    assert changed.status_code == 200
    assert weather.json()["mode"] == "live"
    assert weather.json()["quality"] == "refresh_required"
    assert weather.json()["coverage"] == 0.0
    assert weather.json()["slot_risks"] == {}
    assert weather.json()["tournament_revision"] == changed.json()["revision"]


def test_weather_refresh_records_tournament_revision_and_slot_digest() -> None:
    client = TestClient(
        create_app(weather_service=StubWeatherService()), base_url="https://testserver"
    )
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "global-community-cup"}
    ).json()

    weather = client.post("/api/v1/weather/refresh", json={"mode": "live"}).json()

    assert weather["tournament_revision"] == created["tournament"]["revision"]
    assert len(weather["slot_digest"]) == 64
