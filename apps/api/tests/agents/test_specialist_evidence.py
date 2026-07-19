from app.agents.director import SpecialistRequest
from app.agents.schemas import AgentRole
from app.agents.specialist_evidence import build_specialist_request
from app.agents.strategy import StrategyInput
from app.api.workspace import GuestWorkspaceStore
from app.domain.samples import load_sample


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
