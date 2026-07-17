from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient


def _generated() -> tuple[TestClient, object, str]:
    app = create_app()
    client = TestClient(app, base_url="https://testserver")
    client.post("/api/v1/workspaces", json={"sample_id": "global-community-cup"})
    accepted = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "approval-generation"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()
    run = client.get(f"/api/v1/schedule-runs/{accepted['run_id']}").json()
    return client, app, run["draft_ids"][0]


def test_explicit_approval_creates_version_timestamp_and_audit_event() -> None:
    client, _app, draft_id = _generated()
    approved = client.post(
        f"/api/v1/schedule-drafts/{draft_id}/approve",
        headers={"Idempotency-Key": "approve-original"},
        json={"confirmation": True},
    )
    audit = client.get("/api/v1/audit-events")

    assert approved.status_code == 201
    assert approved.json()["version_number"] == 1
    assert approved.json()["approved_at"].endswith("+00:00")
    assert audit.status_code == 200
    assert audit.json()["items"][-1]["event_type"] == "schedule_approved"
    assert "Version 1" in audit.json()["items"][-1]["summary"]


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
