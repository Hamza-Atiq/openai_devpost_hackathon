from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient


class _NoopWorkflow:
    async def after_generation(self, **_: object) -> tuple[object, ...]:
        return ()

    async def after_repair(self, **_: object) -> tuple[object, ...]:
        return ()


class _CompleteWeather:
    def refresh(self, tournament, *, mode: str, scenario_id: str | None = None):
        risks = {str(slot.id): 25.0 for slot in tournament.slots}
        return {
            "mode": mode,
            "quality": "complete",
            "scenario_id": scenario_id,
            "provider": "deterministic-demo",
            "issued_at": "2026-07-21T00:00:00Z",
            "fetched_at": "2026-07-21T00:00:00Z",
            "coverage": 100.0,
            "slot_risks": risks,
            "slot_details": {},
        }

def _generated() -> tuple[TestClient, object, str]:
    app = create_app()
    client = TestClient(app, base_url="https://testserver")
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "global-community-cup"}
    ).json()
    client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": created["tournament"]["revision"],
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )
    accepted = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "approval-generation"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()
    run = client.get(f"/api/v1/schedule-runs/{accepted['run_id']}").json()
    return client, app, run["draft_ids"][0]


def test_explicit_approval_creates_version_timestamp_and_audit_event() -> None:
    client, _app, draft_id = _generated()
    feedback = client.post(
        f"/api/v1/schedule-drafts/{draft_id}/feedback",
        json={
            "reason": "unfair_rest_distribution",
            "note": "Keep the next comparison focused on group-stage recovery.",
        },
    )
    approved = client.post(
        f"/api/v1/schedule-drafts/{draft_id}/approve",
        headers={"Idempotency-Key": "approve-original"},
        json={"confirmation": True},
    )
    audit = client.get("/api/v1/audit-events")
    exported = client.get("/api/v1/workspace/export")

    assert feedback.status_code == 201
    assert feedback.json()["reason"] == "unfair_rest_distribution"
    assert approved.status_code == 201
    assert approved.json()["version_number"] == 1
    assert approved.json()["approved_at"].endswith("+00:00")
    assert audit.status_code == 200
    event_types = [event["event_type"] for event in audit.json()["items"]]
    assert event_types == [
        "schedule_approved",
        "schedule_feedback_recorded",
        "schedule_options_generated",
        "constraints_confirmed",
        "sample_loaded",
    ]
    assert "Version 1" in audit.json()["items"][0]["summary"]
    assert exported.json()["workspace"]["feedback"][0]["reason"] == "unfair_rest_distribution"
    serialized = str(audit.json()).lower()
    assert "raw_prompt" not in serialized
    assert "hidden_reasoning" not in serialized
    assert "stack_trace" not in serialized


def test_stale_draft_remains_unofficial() -> None:
    client, app, draft_id = _generated()
    workspace = next(iter(app.state.workspace_store._items.values()))
    workspace.tournament = workspace.tournament.model_copy(
        update={"revision": workspace.tournament.revision + 1}
    )

    stale = client.post(
        f"/api/v1/schedule-drafts/{draft_id}/approve",
        headers={"Idempotency-Key": "approve-stale"},
        json={"confirmation": True},
    )

    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_schedule_draft"
    assert workspace.official_versions == []


def test_schedule_weather_uses_the_snapshot_that_generated_its_metrics() -> None:
    app = create_app(
        workflow_orchestrator=_NoopWorkflow(), weather_service=_CompleteWeather()
    )
    client = TestClient(app, base_url="https://testserver")
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "pakistan-community-cup"}
    ).json()
    client.post(
        "/api/v1/weather/demo-scenarios/rain-threshold-v1/activate",
        json={"confirmation": True},
    )
    client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": created["tournament"]["revision"],
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )
    accepted = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "weather-snapshot-generation"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()
    run = client.get(f"/api/v1/schedule-runs/{accepted['run_id']}").json()
    draft_id = run["draft_ids"][0]
    original = client.get(f"/api/v1/weather/schedule?draft_id={draft_id}").json()

    workspace = next(iter(app.state.workspace_store._items.values()))
    workspace.weather = {
        **workspace.weather,
        "quality": "refresh_required",
        "coverage": 0,
        "slot_risks": {},
        "slot_details": {},
    }
    reread = client.get(f"/api/v1/weather/schedule?draft_id={draft_id}").json()

    assert original["coverage"] == 100.0
    assert reread["coverage"] == 100.0
    assert reread["quality"] == original["quality"]
