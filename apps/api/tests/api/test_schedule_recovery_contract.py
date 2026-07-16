from __future__ import annotations

from typing import Any

import app.api.schedules as schedule_routes
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


def test_generation_passes_real_choices_and_weather_penalties_to_profiles(
    monkeypatch,
) -> None:
    app = create_app()
    client = TestClient(app, base_url="https://testserver")
    client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    )
    workspace = next(iter(app.state.workspace_store._items.values()))
    assert workspace.tournament is not None
    workspace.weather["slot_risks"] = {
        str(slot.id): index * 5 for index, slot in enumerate(workspace.tournament.slots)
    }
    captured: dict[str, Any] = {}
    original = schedule_routes.generate_profile_options

    def capture_profile_inputs(*args, **kwargs):
        captured["eligibility"] = args[2]
        captured["component_penalties"] = kwargs.get("component_penalties")
        return original(*args, **kwargs)

    monkeypatch.setattr(schedule_routes, "generate_profile_options", capture_profile_inputs)

    response = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "generation-profile-inputs"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    )

    assert response.status_code == 202
    run = client.get(f"/api/v1/schedule-runs/{response.json()['run_id']}").json()
    metrics_by_profile = {
        option["profile"]: option["metrics"] for option in run["options"]
    }
    signatures = {
        tuple(
            (placement["match_id"], placement["slot_id"])
            for placement in client.get(
                f"/api/v1/schedule-drafts/{draft_id}"
            ).json()["placements"]
        )
        for draft_id in run["draft_ids"]
    }
    assert len(signatures) >= 2
    assert (
        metrics_by_profile["fairness-first"]["group_rest_fairness"]
        >= metrics_by_profile["weather-first"]["group_rest_fairness"]
    )
    eligibility = captured["eligibility"]
    assert all(
        len(slot_ids) == len(workspace.tournament.slots)
        for slot_ids in eligibility.values()
    )
    penalties = captured["component_penalties"]
    assert penalties is not None
    assert set(penalties) == {
        "weather_coverage",
        "rest",
        "venue_balance",
        "slot_balance",
        "organizer_preferences",
        "audience_timing",
    }
    first_match_id = next(iter(eligibility))
    last_slot = workspace.tournament.slots[-1]
    assert penalties["weather_coverage"][(first_match_id, last_slot.id)] == 75


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
