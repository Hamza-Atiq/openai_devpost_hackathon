from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum

from agents import Agent
from pydantic import Field

from app.agents.instructions import build_agent_instructions
from app.agents.schemas import AgentMode, AgentRole, AgentScalar, EvidenceRef
from app.agents.specialist_tools import require_allowed_tools
from app.domain.common import DomainModel


class DirectorTurnInput(DomainModel):
    workspace_summary: Mapping[str, object]
    tournament_revision: int = Field(ge=0)
    user_message: str = Field(min_length=1, max_length=4000)
    pending_actions: tuple[str, ...] = ()
    mode: AgentMode


class ProposedStateChange(DomainModel):
    field: str = Field(min_length=1, max_length=120)
    proposed_value: AgentScalar
    requires_confirmation: bool = True


class SpecialistRequest(DomainModel):
    role: AgentRole
    reason: str = Field(min_length=1, max_length=500)
    required_evidence: tuple[str, ...] = Field(min_length=1)


class DirectorUIAction(StrEnum):
    REVIEW_CONSTRAINTS = "review_constraints"
    GENERATE_SCHEDULES = "generate_schedules"
    REQUEST_SCHEDULE_APPROVAL = "request_schedule_approval"
    REVIEW_REPAIR = "review_repair"


class UIAction(DomainModel):
    action: DirectorUIAction
    target_id: str | None = Field(default=None, max_length=240)
    label: str = Field(min_length=1, max_length=120)


class DirectorTurnOutput(DomainModel):
    message: str = Field(min_length=1, max_length=5000)
    proposed_state_changes: tuple[ProposedStateChange, ...] = ()
    specialist_requests: tuple[SpecialistRequest, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)
    ui_actions: tuple[UIAction, ...] = ()


_ALLOWED_TOOLS = frozenset(
    {
        "read_workspace_summary",
        "rules_specialist",
        "strategy_specialist",
        "weather_specialist",
        "fairness_specialist",
        "recovery_specialist",
        "start_schedule_generation",
        "read_validated_comparison",
        "request_approval_ui",
    }
)


def create_director_agent(
    *,
    model: str = "gpt-5.6",
    tools: Sequence[object] = (),
) -> Agent:
    return Agent(
        name="Tournament Director",
        instructions=build_agent_instructions(AgentRole.TOURNAMENT_DIRECTOR),
        model=model,
        output_type=DirectorTurnOutput,
        tools=require_allowed_tools(tools, _ALLOWED_TOOLS),
    )
