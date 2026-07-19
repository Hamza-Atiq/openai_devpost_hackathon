from __future__ import annotations

from app.agents.schemas import AgentMode
from app.main import create_app
from app.settings import ServerSettings
from fastapi.testclient import TestClient


def _production_settings(*, emergency: bool = False) -> ServerSettings:
    return ServerSettings.from_env(
        {
            "CRICKOPS_ENV": "production",
            "DATABASE_URL": "postgresql://crickops:password@db.example/crickops",
            "OPENAI_API_KEY": "sk-production-fixture-value",
            "CRICKOPS_COOKIE_SECRET": "c" * 32,
            "CRICKOPS_ENCRYPTION_SECRET": "e" * 32,
            "CRICKOPS_ALLOWED_FRONTEND_ORIGINS": "https://crickops.example",
            "CRICKOPS_EMERGENCY_DETERMINISTIC_MODE": str(emergency).lower(),
        }
    )


def test_production_runtime_selects_primary_openai_mode() -> None:
    application = create_app(server_settings=_production_settings())

    assert application.state.operations.mode is AgentMode.GPT_5_6
    assert application.state.operations.provider == "openai"
    assert application.state.operations.model == "gpt-5.6"
    assert application.state.specialist_runtime is not None


def test_emergency_switch_keeps_production_runtime_deterministic() -> None:
    application = create_app(server_settings=_production_settings(emergency=True))

    assert application.state.operations.mode is AgentMode.DETERMINISTIC
    assert application.state.operations.provider is None
    assert application.state.operations.model is None


def test_director_turn_is_a_real_api_capability() -> None:
    assert "/api/v1/director/turn" in create_app().openapi()["paths"]


class StubDirectorRuntime:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def run_turn(self, *, workspace, user_message: str):
        self.messages.append(user_message)
        return {
            "message": "I interpreted this as a preferred evening-slot request.",
            "mode": AgentMode.GPT_5_6,
            "provider": "openai",
            "model": "gpt-5.6",
            "proposed_state_changes": [
                {
                    "field": "priorities.preferred_slots",
                    "proposed_value": "evening",
                    "requires_confirmation": True,
                }
            ],
            "specialist_requests": [],
            "specialist_evidence": [
                {
                    "available": True,
                    "role": "rules_constraint",
                    "mode": "gpt-5.6",
                    "provider": "openai",
                    "model": "gpt-5.6",
                    "occurred_at": "2026-07-19T12:00:00Z",
                    "tournament_revision": workspace.tournament.revision,
                    "invocation_reason": "Interpret preferred evening timing",
                    "validation_status": "valid",
                    "evidence_refs": [],
                    "tool_outcomes": [
                        {
                            "tool_name": "constraint_precheck",
                            "status": "validated",
                            "deterministic_authority": True,
                            "validation_status": "valid",
                            "output_digest": "abc123",
                            "failure_code": None,
                        }
                    ],
                    "consumed_fields": ["current_constraints"],
                    "output": {},
                    "organizer_summary": "Interpreted one preferred constraint.",
                    "attempt_count": 1,
                    "transitions": ["primary_active"],
                }
            ],
            "evidence_refs": [
                {
                    "evidence_id": "workspace-current",
                    "evidence_kind": "workspace_summary",
                    "revision": workspace.tournament.revision,
                    "consumed_fields": ["priorities", "slots"],
                }
            ],
            "ui_actions": [
                {
                    "action": "review_constraints",
                    "target_id": None,
                    "label": "Review interpreted constraints",
                }
            ],
            "attempt_count": 1,
            "transitions": ["primary_active"],
            "unavailable_reason": None,
        }


def test_director_turn_invokes_runtime_and_audits_safe_provenance() -> None:
    runtime = StubDirectorRuntime()
    application = create_app(director_runtime=runtime)
    client = TestClient(application, base_url="https://testserver")
    created = client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    )
    assert created.status_code == 201

    response = client.post(
        "/api/v1/director/turn",
        json={"message": "Prefer evening matches where possible."},
    )

    assert response.status_code == 200
    assert runtime.messages == ["Prefer evening matches where possible."]
    document = response.json()
    assert document["mode"] == "gpt-5.6"
    assert document["provider"] == "openai"
    assert document["model"] == "gpt-5.6"
    assert document["proposed_state_changes"][0]["requires_confirmation"] is True
    assert "raw_prompt" not in response.text
    audit = client.get("/api/v1/audit-events").json()["items"]
    assert audit[0]["event_type"] == "director_turn_completed"
    assert audit[0]["agent_provenance"] == {
        "role": "tournament_director",
        "provider": "openai",
        "model": "gpt-5.6",
        "validation_status": "valid",
    }
    specialist = audit[0]["structured_payload"]["specialist_evidence"][0]
    assert specialist["role"] == "rules_constraint"
    assert specialist["tool_outcomes"][0]["status"] == "validated"


def test_director_turn_in_deterministic_mode_never_fabricates_a_reply() -> None:
    application = create_app()
    client = TestClient(application, base_url="https://testserver")
    client.post("/api/v1/workspaces", json={"sample_id": "global-community-cup"})

    response = client.post(
        "/api/v1/director/turn",
        json={"message": "Move important matches to the evening."},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "deterministic"
    assert response.json()["message"] is None
    assert response.json()["fabricated_agent_response"] is False
    assert response.json()["unavailable_reason"]
