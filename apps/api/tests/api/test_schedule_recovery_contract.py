from __future__ import annotations

from typing import Any

import app.api.schedules as schedule_routes
import pytest
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


def client_with_sample(*, confirm_constraints: bool = True) -> TestClient:
    client = TestClient(create_app(), base_url="https://testserver")
    created = client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    ).json()
    if confirm_constraints:
        confirmed = client.post(
            "/api/v1/constraints/confirm",
            json={
                "confirmation": True,
                "expected_revision": created["tournament"]["revision"],
                "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
            },
        )
        assert confirmed.status_code == 200
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
    created = client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    ).json()
    confirmed = client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": created["tournament"]["revision"],
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )
    assert confirmed.status_code == 200
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
    metrics_by_profile = {option["profile"]: option["metrics"] for option in run["options"]}
    signatures = {
        tuple(
            (placement["match_id"], placement["slot_id"])
            for placement in client.get(f"/api/v1/schedule-drafts/{draft_id}").json()["placements"]
        )
        for draft_id in run["draft_ids"]
    }
    assert len(signatures) >= 2
    assert metrics_by_profile["fairness-first"] != metrics_by_profile["weather-first"]
    eligibility = captured["eligibility"]
    assert all(
        len(slot_ids) == len(workspace.tournament.slots) for slot_ids in eligibility.values()
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
    assert penalties["weather_coverage"][(first_match_id, last_slot.id)] == 100


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


def _approved_client() -> tuple[TestClient, dict[str, Any]]:
    client = client_with_sample()
    accepted = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "generation-disruption-validation"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()
    draft_id = client.get(f"/api/v1/schedule-runs/{accepted['run_id']}").json()[
        "draft_ids"
    ][0]
    draft = client.get(f"/api/v1/schedule-drafts/{draft_id}").json()
    approved = client.post(
        f"/api/v1/schedule-drafts/{draft_id}/approve",
        headers={"Idempotency-Key": "approval-disruption-validation"},
        json={"confirmation": True},
    )
    assert approved.status_code == 201
    return client, draft


def test_disruption_rejects_slot_that_does_not_belong_to_tournament() -> None:
    client, _draft = _approved_client()

    response = client.post(
        "/api/v1/disruptions",
        json={
            "type": "rain",
            "unavailable_slot_ids": ["01890f3e-0001-7000-8000-ffffffffffff"],
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_disruption_slots"
    assert "do not belong" in response.json()["detail"]


def test_infeasible_repair_records_conflict_evidence_and_concrete_remedies() -> None:
    client, draft = _approved_client()
    workspace = next(iter(client.app.state.workspace_store._items.values()))
    assert workspace.tournament is not None
    occupied = {placement["slot_id"] for placement in draft["placements"]}
    workspace.tournament = workspace.tournament.model_copy(
        update={
            "slots": tuple(
                slot for slot in workspace.tournament.slots if str(slot.id) in occupied
            )
        }
    )
    blocked_slot = draft["placements"][0]["slot_id"]
    disruption = client.post(
        "/api/v1/disruptions",
        json={"type": "rain", "unavailable_slot_ids": [blocked_slot]},
    )
    assert disruption.status_code == 201

    response = client.post(
        f"/api/v1/disruptions/{disruption.json()['disruption_id']}/repair-runs"
    )

    assert response.status_code == 422
    assert response.json()["code"] == "repair_infeasible"
    assert response.json()["evidence"]
    assert {item["code"] for item in response.json()["remedies"]} >= {
        "add_venue_slots",
        "extend_tournament_window",
    }
    audit = client.get("/api/v1/audit-events").json()["items"]
    assert audit[0]["event_type"] == "repair_infeasible"
    assert audit[0]["structured_payload"]["official_schedule_preserved"] is True


@pytest.mark.parametrize("disruption_type", ["rain", "venue_unavailability"])
def test_supported_disruption_produces_validated_minimum_change_diff(
    disruption_type: str,
) -> None:
    client = client_with_sample(confirm_constraints=False)
    correlation_id = "018f6c7a-9a4b-7c1d-8e2f-123456789abc"
    workspace = client.get("/api/v1/workspace").json()
    confirmed = client.post(
        "/api/v1/constraints/confirm",
        headers={"X-Correlation-ID": correlation_id},
        json={
            "confirmation": True,
            "expected_revision": workspace["tournament"]["revision"],
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )
    assert confirmed.status_code == 200
    run_id = client.post(
        "/api/v1/schedule-runs",
        headers={
            "Idempotency-Key": "generation-repair",
            "X-Correlation-ID": correlation_id,
        },
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()["run_id"]
    draft_ids = client.get(f"/api/v1/schedule-runs/{run_id}").json()["draft_ids"]
    draft_id = draft_ids[0]
    draft = client.get(f"/api/v1/schedule-drafts/{draft_id}").json()
    official = client.post(
        f"/api/v1/schedule-drafts/{draft_id}/approve",
        headers={
            "Idempotency-Key": "approval-repair",
            "X-Correlation-ID": correlation_id,
        },
        json={"confirmation": True},
    ).json()
    disruption = client.post(
        "/api/v1/disruptions",
        headers={"X-Correlation-ID": correlation_id},
        json={
            "type": disruption_type,
            "unavailable_slot_ids": [draft["placements"][-1]["slot_id"]],
        },
    ).json()

    repair = client.post(
        f"/api/v1/disruptions/{disruption['disruption_id']}/repair-runs",
        headers={"X-Correlation-ID": correlation_id},
    )
    diff = client.get(f"/api/v1/schedule-diffs/{repair.json()['draft_id']}")

    assert repair.status_code == 202
    assert repair.json()["status"] == "completed"
    assert diff.status_code == 200
    assert diff.json()["moved"]
    assert diff.json()["unchanged"]
    assert diff.json()["validation_valid"] is True
    assert len(diff.json()["fixture_views"]) == 15
    moved_views = [item for item in diff.json()["fixture_views"] if item["change"] == "moved"]
    assert moved_views
    assert all(item["before"] and item["after"] for item in moved_views)
    if disruption_type == "venue_unavailability":
        rejected = client.post(f"/api/v1/schedule-drafts/{draft_ids[2]}/reject")
        rejected_approval = client.post(
            f"/api/v1/schedule-drafts/{draft_ids[2]}/approve",
            headers={"Idempotency-Key": "cannot-approve-rejected"},
            json={"confirmation": True},
        )
        assert rejected.status_code == 204
        assert rejected_approval.status_code == 409
        assert rejected_approval.json()["code"] == "draft_not_approvable"
        client.post(
            f"/api/v1/schedule-drafts/{draft_ids[1]}/approve",
            headers={"Idempotency-Key": "newer-official"},
            json={"confirmation": True},
        )
        stale = client.post(
            f"/api/v1/schedule-drafts/{repair.json()['draft_id']}/approve",
            headers={"Idempotency-Key": "approve-stale-repair"},
            json={"confirmation": True},
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "stale_official_baseline"
        return
    approved = client.post(
        f"/api/v1/schedule-drafts/{repair.json()['draft_id']}/approve",
        headers={
            "Idempotency-Key": f"approve-repair-{disruption_type}",
            "X-Correlation-ID": correlation_id,
        },
        json={"confirmation": True},
    )
    replay = client.post(
        f"/api/v1/schedule-drafts/{repair.json()['draft_id']}/approve",
        headers={"Idempotency-Key": f"approve-repair-{disruption_type}"},
        json={"confirmation": True},
    )
    assert approved.status_code == 201
    assert approved.json()["version_number"] == 2
    assert replay.json()["version_id"] == approved.json()["version_id"]
    audit = client.get("/api/v1/audit-events")
    assert audit.status_code == 200
    assert [event["event_type"] for event in audit.json()["items"]] == [
        "schedule_approved",
        "repair_generated",
        "disruption_declared",
        "schedule_approved",
        "schedule_options_generated",
        "constraints_confirmed",
    ]
    observations = client.app.state.observability.records_for(correlation_id)
    assert {record.component for record in observations} >= {
        "http",
        "weather",
        "solver",
        "validator",
        "database",
        "approval",
        "audit",
        "hero",
    }
    assert client.app.state.observability.metric("hero_flow_success_total") == 1
    restored = client.post(
        f"/api/v1/schedule-versions/{official['version_id']}/restore",
        headers={"Idempotency-Key": "restore-original"},
        json={"confirmation": True},
    )
    assert restored.status_code == 201
    assert restored.json()["version_number"] == 3
    assert restored.json()["approved_draft_id"] == draft_id
