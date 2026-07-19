from __future__ import annotations

from collections.abc import Mapping

from app.main import create_app
from fastapi.testclient import TestClient


class StubWorkflowOrchestrator:
    async def after_generation(self, *, workspace, run) -> tuple[Mapping[str, object], ...]:
        del workspace, run
        return tuple(
            {
                "role": role,
                "available": True,
                "provider": "openai",
                "model": "gpt-5.6",
                "validation_status": "valid",
                "tool_outcomes": [{"status": "validated"}],
            }
            for role in (
                "scheduling_strategy",
                "weather_intelligence",
                "fairness_logistics",
            )
        )

    async def after_repair(
        self, *, workspace, draft_id, disruption, diff
    ) -> tuple[Mapping[str, object], ...]:
        del workspace, draft_id, disruption, diff
        return tuple(
            {
                "role": role,
                "available": True,
                "provider": "openai",
                "model": "gpt-5.6",
                "validation_status": "valid",
                "tool_outcomes": [{"status": "validated"}],
            }
            for role in (
                "weather_intelligence",
                "disruption_recovery",
                "fairness_logistics",
            )
        )


class FailingWorkflowOrchestrator:
    async def after_generation(self, *, workspace, run):
        del workspace, run
        raise TimeoutError("provider unavailable")


def _confirmed_client(orchestrator) -> TestClient:
    client = TestClient(
        create_app(workflow_orchestrator=orchestrator), base_url="https://testserver"
    )
    created = client.post(
        "/api/v1/workspaces", json={"sample_id": "global-community-cup"}
    ).json()
    response = client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": created["tournament"]["revision"],
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )
    assert response.status_code == 200
    return client


def test_generation_records_meaningful_specialist_sequence() -> None:
    client = _confirmed_client(StubWorkflowOrchestrator())
    response = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "specialist-generation"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    )
    assert response.status_code == 202

    run = client.get(f"/api/v1/schedule-runs/{response.json()['run_id']}").json()
    assert [item["role"] for item in run["specialist_evidence"]] == [
        "scheduling_strategy",
        "weather_intelligence",
        "fairness_logistics",
    ]
    assert run["agent_status"] == "complete"
    audit = client.get("/api/v1/audit-events").json()["items"][0]
    assert len(audit["structured_payload"]["specialist_evidence"]) == 3


def test_agent_outage_keeps_valid_generation_available() -> None:
    client = _confirmed_client(FailingWorkflowOrchestrator())
    response = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "specialist-outage"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    )

    assert response.status_code == 202
    run = client.get(f"/api/v1/schedule-runs/{response.json()['run_id']}").json()
    assert all(item["validation_valid"] for item in run["options"])
    assert run["agent_status"] == "unavailable"
    assert run["specialist_evidence"] == []


def test_repair_records_weather_recovery_and_fairness_sequence() -> None:
    client = _confirmed_client(StubWorkflowOrchestrator())
    generated = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "specialist-repair-generation"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()
    run = client.get(f"/api/v1/schedule-runs/{generated['run_id']}").json()
    draft_id = run["draft_ids"][0]
    draft = client.get(f"/api/v1/schedule-drafts/{draft_id}").json()
    approved = client.post(
        f"/api/v1/schedule-drafts/{draft_id}/approve",
        headers={"Idempotency-Key": "specialist-repair-approval"},
        json={"confirmation": True},
    )
    assert approved.status_code == 201
    disruption = client.post(
        "/api/v1/disruptions",
        json={
            "type": "rain",
            "unavailable_slot_ids": [draft["placements"][-1]["slot_id"]],
        },
    )
    assert disruption.status_code == 201

    repair = client.post(
        f"/api/v1/disruptions/{disruption.json()['disruption_id']}/repair-runs"
    )

    assert repair.status_code == 202
    assert [item["role"] for item in repair.json()["specialist_evidence"]] == [
        "weather_intelligence",
        "disruption_recovery",
        "fairness_logistics",
    ]
    assert repair.json()["agent_status"] == "complete"
