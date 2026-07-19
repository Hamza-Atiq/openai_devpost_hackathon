import asyncio
from types import SimpleNamespace

from app.agents.director import SpecialistRequest
from app.agents.runtime import normalize_specialist_requests
from app.agents.schemas import AgentRole
from app.agents.specialist_evidence import build_specialist_request
from app.agents.strategy import StrategyInput
from app.agents.workflow_orchestrator import WorkflowAgentOrchestrator
from app.api.workspace import GuestWorkspaceStore
from app.domain.samples import load_sample
from app.main import create_app
from fastapi.testclient import TestClient


def test_strategy_request_uses_latest_validated_schedule_metrics() -> None:
    store = GuestWorkspaceStore()
    _token, workspace = store.create(load_sample("global-community-cup"))
    workspace.schedule_runs["run-1"] = {
        "status": "completed",
        "options": [
            {
                "draft_id": "draft-balanced",
                "profile": "balanced",
                "validation_valid": True,
                "metrics": {
                    "weather_risk": 18.5,
                    "group_rest_fairness": 91.0,
                    "venue_balance": 100.0,
                },
            },
            {
                "draft_id": "draft-weather",
                "profile": "weather-first",
                "validation_valid": True,
                "metrics": {
                    "weather_risk": 12.0,
                    "group_rest_fairness": 84.0,
                    "venue_balance": 95.0,
                },
            },
        ],
    }

    request = build_specialist_request(
        workspace,
        SpecialistRequest(
            role=AgentRole.SCHEDULING_STRATEGY,
            reason="Compare validated schedule options",
            required_evidence=("validated_schedule_comparison",),
        ),
        "Which option has the lowest weather risk and why?",
    )

    assert request is not None
    assert isinstance(request.payload, StrategyInput)
    assert request.payload.validated_metrics is not None
    assert request.payload.validated_metrics["weather-first"]["weather_risk"] == 12.0
    assert request.consumed_fields == ("validated_metrics", "confirmed_constraints")


def test_option_metric_question_always_routes_to_strategy_evidence() -> None:
    store = GuestWorkspaceStore()
    _token, workspace = store.create(load_sample("global-community-cup"))
    workspace.schedule_runs["run-1"] = {
        "status": "completed",
        "options": [{"profile": "balanced", "validation_valid": True, "metrics": {}}],
    }

    requests = normalize_specialist_requests(
        (
            SpecialistRequest(
                role=AgentRole.WEATHER_INTELLIGENCE,
                reason="Explain weather",
                required_evidence=("weather",),
            ),
        ),
        workspace=workspace,
        user_message="Which option has the lowest weather risk and why?",
    )

    assert AgentRole.SCHEDULING_STRATEGY in {request.role for request in requests}


def test_rules_request_uses_current_tournament_revision_and_user_text() -> None:
    store = GuestWorkspaceStore()
    _token, workspace = store.create(load_sample("global-community-cup"))

    request = build_specialist_request(
        workspace,
        SpecialistRequest(
            role=AgentRole.RULES_CONSTRAINT,
            reason="Interpret organizer request",
            required_evidence=("current_constraints",),
        ),
        "Prefer evening matches.",
    )

    assert request is not None
    assert request.payload.user_text == "Prefer evening matches."
    assert request.tournament_revision == workspace.tournament.revision


def test_generation_orchestrator_consumes_validated_application_evidence() -> None:
    client = TestClient(create_app(), base_url="https://testserver")
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
        headers={"Idempotency-Key": "orchestrator-evidence"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    ).json()
    workspace = next(iter(client.app.state.workspace_store._items.values()))
    run = workspace.schedule_runs[accepted["run_id"]]
    requests = []

    class CapturingRuntime:
        async def run(self, request):
            requests.append(request)
            return SimpleNamespace(
                model_dump=lambda **_kwargs: {
                    "role": request.role.value,
                    "available": True,
                }
            )

    evidence = asyncio.run(
        WorkflowAgentOrchestrator(CapturingRuntime()).after_generation(
            workspace=workspace, run=run
        )
    )

    assert [request.role for request in requests] == [
        AgentRole.SCHEDULING_STRATEGY,
        AgentRole.WEATHER_INTELLIGENCE,
        AgentRole.FAIRNESS_LOGISTICS,
    ]
    assert len(evidence) == 3
    assert requests[0].payload.validated_metrics is not None
    assert requests[1].payload.fixture_risks
    assert requests[2].payload.validation_valid is True
