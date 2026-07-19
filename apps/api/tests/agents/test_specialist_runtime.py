from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.agents.provider import AgentProviderRouter
from app.agents.rules import ConstraintInterpretationInput, ConstraintInterpretationOutput
from app.agents.schemas import AgentRole, ValidationStatus
from app.agents.specialist_runtime import SpecialistRunRequest, SpecialistRuntime


def test_specialist_runtime_executes_rules_agent_and_records_consumed_evidence() -> None:
    calls: list[object] = []

    async def runner(agent, input_value, **kwargs):
        calls.append(agent)
        return SimpleNamespace(
            final_output={
                "proposed_additions": [],
                "proposed_changes": [],
                "ambiguities": [],
                "contradictions": [],
                "clarification_question": None,
                "evidence_refs": [
                    {
                        "evidence_id": "constraint-precheck:r4",
                        "evidence_kind": "constraint_precheck",
                        "revision": 4,
                        "consumed_fields": ["current_constraints", "tournament_context"],
                    }
                ],
            }
        )

    runtime = SpecialistRuntime(
        provider_router=AgentProviderRouter(openai_api_key="test-key-long-enough"),
        runner=runner,
    )
    result = asyncio.run(
        runtime.run(
            SpecialistRunRequest(
                role=AgentRole.RULES_CONSTRAINT,
                payload=ConstraintInterpretationInput(
                    current_constraints=("fixed-format",),
                    user_text="Prefer evening matches.",
                    tournament_context={"revision": 4},
                ),
                invocation_reason="Interpret an organizer preference",
                tournament_revision=4,
                consumed_fields=("current_constraints", "tournament_context"),
                tool_name="constraint_precheck",
                deterministic_authority=True,
            )
        )
    )

    assert calls[0].name == "Rules and Constraint Specialist"
    assert result.available is True
    assert result.role is AgentRole.RULES_CONSTRAINT
    assert result.provider == "openai"
    assert result.model == "gpt-5.6"
    assert result.validation_status is ValidationStatus.VALID
    assert result.consumed_fields == ("current_constraints", "tournament_context")
    assert result.tool_outcomes[0].tool_name == "constraint_precheck"
    assert result.output == ConstraintInterpretationOutput.model_validate(
        {
            "proposed_additions": [],
            "proposed_changes": [],
            "ambiguities": [],
            "contradictions": [],
            "clarification_question": None,
            "evidence_refs": [
                {
                    "evidence_id": "constraint-precheck:r4",
                    "evidence_kind": "constraint_precheck",
                    "revision": 4,
                    "consumed_fields": ["current_constraints", "tournament_context"],
                }
            ],
        }
    ).model_dump(mode="json")


def test_specialist_runtime_uses_every_specialist_factory() -> None:
    assert set(SpecialistRuntime.supported_roles()) == {
        AgentRole.RULES_CONSTRAINT,
        AgentRole.SCHEDULING_STRATEGY,
        AgentRole.WEATHER_INTELLIGENCE,
        AgentRole.FAIRNESS_LOGISTICS,
        AgentRole.DISRUPTION_RECOVERY,
    }
