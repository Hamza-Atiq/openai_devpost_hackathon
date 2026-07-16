from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient

SCHEDULE_PATHS = {
    "/api/v1/schedule-runs",
    "/api/v1/schedule-runs/{run_id}",
    "/api/v1/schedule-runs/{run_id}/events",
    "/api/v1/schedule-drafts/{draft_id}",
    "/api/v1/schedule-comparisons",
    "/api/v1/schedule-drafts/{draft_id}/feedback",
    "/api/v1/schedule-drafts/{draft_id}/approve",
    "/api/v1/schedule-drafts/{draft_id}/reject",
    "/api/v1/schedule-edits",
    "/api/v1/schedule-edits/{edit_id}/confirm",
    "/api/v1/schedule-edits/{edit_id}",
    "/api/v1/disruptions",
    "/api/v1/disruptions/{disruption_id}/repair-runs",
    "/api/v1/schedule-diffs/{draft_id}",
}


def client_with_sample() -> TestClient:
    client = TestClient(create_app(), base_url="https://testserver")
    client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    )
    return client


def test_openapi_exposes_schedule_and_recovery_routes() -> None:
    assert SCHEDULE_PATHS.issubset(create_app().openapi()["paths"])


def test_generation_is_idempotent_and_returns_three_validated_drafts() -> None:
    client = client_with_sample()
    headers = {"Idempotency-Key": "generation-001"}

    first = client.post(
        "/api/v1/schedule-runs",
        headers=headers,
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    )
    replay = client.post(
        "/api/v1/schedule-runs",
        headers=headers,
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    )
    run = client.get(f"/api/v1/schedule-runs/{first.json()['run_id']}")

    assert first.status_code == 202
    assert replay.json()["run_id"] == first.json()["run_id"]
    assert run.json()["status"] == "completed"
    assert len(run.json()["draft_ids"]) == 3
    assert all(item["validation_valid"] for item in run.json()["options"])


def test_stale_generation_is_rejected_and_queued_run_can_be_cancelled() -> None:
    client = client_with_sample()
    stale = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "stale-generation"},
        json={
            "profiles": ["balanced", "weather_first", "fairness_first"],
            "expected_revision": 99,
        },
    )
    accepted = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "cancel-generation"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()
    cancelled = client.delete(f"/api/v1/schedule-runs/{accepted['run_id']}")

    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_tournament_revision"
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_comparison_and_approval_require_owned_validated_draft() -> None:
    client = client_with_sample()
    accepted = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "generation-002"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()
    comparison = client.get(
        "/api/v1/schedule-comparisons",
        params={"run_id": accepted["run_id"]},
    )
    draft_id = comparison.json()["options"][0]["draft_id"]
    approval = client.post(
        f"/api/v1/schedule-drafts/{draft_id}/approve",
        headers={"Idempotency-Key": "approval-001"},
        json={"confirmation": True},
    )

    assert comparison.status_code == 200
    assert comparison.json()["metric_version"] == "schedule-metrics/v1"
    assert approval.status_code == 201
    assert approval.json()["version_number"] == 1


def test_disruption_rejects_workspace_without_official_baseline() -> None:
    response = client_with_sample().post(
        "/api/v1/disruptions",
        json={"type": "rain", "unavailable_slot_ids": ["slot-1"]},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "official_schedule_required"


def test_rain_disruption_produces_validated_minimum_change_diff() -> None:
    client = client_with_sample()
    run_id = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "generation-repair"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()["run_id"]
    draft_id = client.get(f"/api/v1/schedule-runs/{run_id}").json()["draft_ids"][0]
    draft = client.get(f"/api/v1/schedule-drafts/{draft_id}").json()
    client.post(
        f"/api/v1/schedule-drafts/{draft_id}/approve",
        headers={"Idempotency-Key": "approval-repair"},
        json={"confirmation": True},
    )
    disruption = client.post(
        "/api/v1/disruptions",
        json={
            "type": "rain",
            "unavailable_slot_ids": [draft["placements"][-1]["slot_id"]],
        },
    ).json()

    repair = client.post(
        f"/api/v1/disruptions/{disruption['disruption_id']}/repair-runs"
    )
    diff = client.get(f"/api/v1/schedule-diffs/{repair.json()['draft_id']}")

    assert repair.status_code == 202
    assert repair.json()["status"] == "completed"
    assert diff.status_code == 200
    assert diff.json()["moved"]
    assert diff.json()["unchanged"]
