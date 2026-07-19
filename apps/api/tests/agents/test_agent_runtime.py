from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.agents.provider import AgentProviderRouter
from app.agents.rules import ConstraintInterpretationInput
from app.agents.runtime import DirectorRuntime
from app.agents.schemas import AgentMode, AgentRole, ValidationStatus
from app.agents.specialist_runtime import (
    SpecialistRunRequest,
    SpecialistRuntimeResult,
)
from app.api.workspace import GuestWorkspaceStore
from app.domain.samples import load_sample


def test_director_runtime_executes_agents_sdk_runner_with_primary_provider() -> None:
    calls: list[dict[str, object]] = []

    async def runner(agent, input_value, **kwargs):
        calls.append(
            {
                "agent": agent,
                "input": input_value,
                "max_turns": kwargs["max_turns"],
                "run_config": kwargs["run_config"],
            }
        )
        return SimpleNamespace(
            final_output={
                "message": "Review the evening-slot preference in structured controls.",
                "proposed_state_changes": [
                    {
                        "field": "priorities.preferred_slots",
                        "proposed_value": "evening",
                        "requires_confirmation": True,
                    }
                ],
                "specialist_requests": [],
                "evidence_refs": [
                    {
                        "evidence_id": "workspace-current",
                        "evidence_kind": "workspace_summary",
                        "revision": 0,
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
            }
        )

    store = GuestWorkspaceStore()
    _token, workspace = store.create(load_sample("global-community-cup"))
    runtime = DirectorRuntime(
        provider_router=AgentProviderRouter(openai_api_key="test-key-long-enough"),
        runner=runner,
    )

    result = asyncio.run(
        runtime.run_turn(
            workspace=workspace,
            user_message="Prefer evening matches where possible.",
        )
    )

    assert result.mode is AgentMode.GPT_5_6
    assert result.provider == "openai"
    assert result.model == "gpt-5.6"
    assert result.message and "structured controls" in result.message
    assert calls[0]["agent"].name == "Tournament Director"
    assert calls[0]["max_turns"] == 8
    assert calls[0]["run_config"].trace_include_sensitive_data is False
    assert calls[0]["run_config"].model_provider is not None


def test_director_runs_requested_specialist_then_synthesizes_grounded_reply() -> None:
    calls: list[dict[str, object]] = []

    async def runner(agent, input_value, **kwargs):
        calls.append({"agent": agent, "input": input_value})
        if len(calls) == 1:
            return SimpleNamespace(
                final_output={
                    "message": "I need the Rules specialist to interpret that preference.",
                    "specialist_requests": [
                        {
                            "role": "rules_constraint",
                            "reason": "Interpret preferred evening timing",
                            "required_evidence": ["current_constraints", "tournament_context"],
                        }
                    ],
                    "evidence_refs": [
                        {
                            "evidence_id": "workspace-current",
                            "evidence_kind": "workspace_summary",
                            "revision": 0,
                            "consumed_fields": ["priorities"],
                        }
                    ],
                }
            )
        return SimpleNamespace(
            final_output={
                "message": "I interpreted evening timing as a preferred constraint for review.",
                "specialist_requests": [],
                "evidence_refs": [
                    {
                        "evidence_id": "constraint-precheck:r0",
                        "evidence_kind": "constraint_precheck",
                        "revision": 0,
                        "consumed_fields": ["proposed_changes"],
                    }
                ],
            }
        )

    class StubSpecialists:
        async def run(self, request: SpecialistRunRequest) -> SpecialistRuntimeResult:
            assert request.role is AgentRole.RULES_CONSTRAINT
            return SpecialistRuntimeResult(
                available=True,
                role=request.role,
                mode=AgentMode.GPT_5_6,
                provider="openai",
                model="gpt-5.6",
                occurred_at="2026-07-19T12:00:00Z",
                tournament_revision=0,
                invocation_reason=request.invocation_reason,
                validation_status=ValidationStatus.VALID,
                evidence_refs=(
                    {
                        "evidence_id": "constraint-precheck:r0",
                        "evidence_kind": "constraint_precheck",
                        "revision": 0,
                        "consumed_fields": ["proposed_changes"],
                    },
                ),
                consumed_fields=("current_constraints", "tournament_context"),
                output={"proposed_changes": [{"key": "preferred_slot", "value": "evening"}]},
                organizer_summary="Interpreted one preferred constraint.",
                attempt_count=1,
            )

    def build_request(_workspace, specialist_request, user_message):
        return SpecialistRunRequest(
            role=specialist_request.role,
            payload=ConstraintInterpretationInput(
                current_constraints=("fixed-format",),
                user_text=user_message,
                tournament_context={"revision": 0},
            ),
            invocation_reason=specialist_request.reason,
            tournament_revision=0,
            consumed_fields=("current_constraints", "tournament_context"),
            tool_name="constraint_precheck",
            deterministic_authority=True,
        )

    store = GuestWorkspaceStore()
    _token, workspace = store.create(load_sample("global-community-cup"))
    runtime = DirectorRuntime(
        provider_router=AgentProviderRouter(openai_api_key="test-key-long-enough"),
        runner=runner,
        specialist_runtime=StubSpecialists(),
        specialist_request_builder=build_request,
    )

    result = asyncio.run(
        runtime.run_turn(workspace=workspace, user_message="Prefer evening matches.")
    )

    assert len(calls) == 2
    assert "specialist_evidence" in str(calls[1]["input"])
    assert result.message and "preferred constraint" in result.message
    assert result.specialist_evidence[0]["role"] == "rules_constraint"
