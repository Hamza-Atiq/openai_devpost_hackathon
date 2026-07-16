from __future__ import annotations

from collections.abc import Mapping, Sequence

from agents import Agent
from pydantic import Field

from app.agents.instructions import build_agent_instructions
from app.agents.schemas import AgentRole, EvidenceRef
from app.agents.specialist_tools import require_allowed_tools
from app.domain.common import DomainModel
from app.domain.schedules import ScheduleProfile


class StrategyInput(DomainModel):
    confirmed_constraints: tuple[str, ...]
    priorities: Mapping[str, bool | int]
    available_profiles: tuple[ScheduleProfile, ...]
    validated_metrics: Mapping[ScheduleProfile, Mapping[str, float]] | None = None


class StrategyOutput(DomainModel):
    profile_requests: tuple[ScheduleProfile, ...]
    comparison_commentary: str | None = Field(default=None, max_length=2000)
    recommendation: ScheduleProfile | None = None
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)


def validate_strategy_output(
    turn_input: StrategyInput,
    output: StrategyOutput,
) -> StrategyOutput:
    if not set(output.profile_requests).issubset(turn_input.available_profiles):
        raise ValueError("strategy requested a profile outside the available catalog")
    if output.recommendation is not None:
        if turn_input.validated_metrics is None:
            raise ValueError("strategy recommendation requires validated metrics")
        if output.recommendation not in turn_input.validated_metrics:
            raise ValueError("recommended profile has no validated metrics")
        if not any(
            ref.evidence_kind == "validated_schedule_comparison" for ref in output.evidence_refs
        ):
            raise ValueError("recommendation must consume validated comparison evidence")
    if output.comparison_commentary is not None and turn_input.validated_metrics is None:
        raise ValueError("comparison commentary requires validated metrics")
    return output


_ALLOWED_TOOLS = frozenset(
    {"read_profile_catalog", "generate_schedule_profiles", "read_validated_comparison"}
)


def create_strategy_agent(
    *,
    model: str = "gpt-5.6",
    tools: Sequence[object] = (),
) -> Agent:
    return Agent(
        name="Scheduling Strategy Specialist",
        instructions=build_agent_instructions(AgentRole.SCHEDULING_STRATEGY),
        model=model,
        output_type=StrategyOutput,
        tools=require_allowed_tools(tools, _ALLOWED_TOOLS),
    )
