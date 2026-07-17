from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from agents import RunContextWrapper, function_tool
from app.agents.guarded_tool import (
    AgentToolContext,
    GuardedToolPolicy,
    ToolAuthorizationError,
    ToolValidationError,
    guard_function_tool,
)
from app.agents.schemas import AgentRole, ToolOutcomeStatus
from app.observability.context import observation_scope
from app.observability.recorder import ObservabilityRecorder
from pydantic import BaseModel


class SolveRequest(BaseModel):
    tournament_revision: int


@function_tool
async def solve_schedule(
    context: RunContextWrapper[AgentToolContext], request: SolveRequest
) -> str:
    """Run the authoritative deterministic schedule service."""
    return f"validated:{request.tournament_revision}:{context.context.role}"


POLICY = GuardedToolPolicy(
    authorized_roles=frozenset({AgentRole.SCHEDULING_STRATEGY}),
    deterministic_authority=True,
    output_validator=lambda value: str(value).startswith("validated:"),
)


def _context(role: AgentRole) -> AgentToolContext:
    return AgentToolContext(role=role, provider="openai", model="gpt-5.6")


def _tool_context(context: AgentToolContext) -> SimpleNamespace:
    return SimpleNamespace(context=context, tool_name="solve_schedule", run_config=None)


def test_authorized_tool_records_traceable_validated_outcome() -> None:
    context = _context(AgentRole.SCHEDULING_STRATEGY)
    guarded = guard_function_tool(solve_schedule, POLICY)
    recorder = ObservabilityRecorder()

    with observation_scope("018f6c7a-9a4b-7c1d-8e2f-123456789abc", recorder):
        output = asyncio.run(
            guarded.on_invoke_tool(
                _tool_context(context),
                '{"request": {"tournament_revision": 3}}',
            )
        )

    assert str(output).startswith("validated:3")
    assert context.tool_outcomes[0].tool_name == "solve_schedule"
    assert context.tool_outcomes[0].status is ToolOutcomeStatus.VALIDATED
    assert context.tool_outcomes[0].deterministic_authority is True
    tool_record = recorder.records_for("018f6c7a-9a4b-7c1d-8e2f-123456789abc")[0]
    assert tool_record.component == "tool"
    assert tool_record.outcome == "validated"
    assert tool_record.metadata == {
        "tool_name": "solve_schedule",
        "role": "scheduling_strategy",
        "provider": "openai",
        "model": "gpt-5.6",
        "deterministic_authority": True,
    }
    assert "tournament_revision" not in str(tool_record.metadata)


def test_unauthorized_role_cannot_invoke_tool() -> None:
    guarded = guard_function_tool(solve_schedule, POLICY)

    with pytest.raises(ToolAuthorizationError):
        asyncio.run(
            guarded.on_invoke_tool(
                _tool_context(_context(AgentRole.WEATHER_INTELLIGENCE)),
                '{"request": {"tournament_revision": 3}}',
            )
        )


def test_invalid_tool_output_is_rejected_and_recorded() -> None:
    invalid_policy = GuardedToolPolicy(
        authorized_roles=frozenset({AgentRole.SCHEDULING_STRATEGY}),
        deterministic_authority=True,
        output_validator=lambda _value: False,
    )
    context = _context(AgentRole.SCHEDULING_STRATEGY)
    guarded = guard_function_tool(solve_schedule, invalid_policy)

    with pytest.raises(ToolValidationError):
        asyncio.run(
            guarded.on_invoke_tool(
                _tool_context(context), '{"request": {"tournament_revision": 3}}'
            )
        )
    assert context.tool_outcomes[0].status is ToolOutcomeStatus.REJECTED
