from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from agents import Agent
from pydantic import Field

from app.agents.instructions import build_agent_instructions
from app.agents.schemas import AgentRole, EvidenceRef
from app.agents.specialist_tools import require_allowed_tools
from app.domain.common import DomainModel


class ConstraintInterpretationInput(DomainModel):
    current_constraints: tuple[str, ...]
    user_text: str = Field(min_length=1, max_length=4000)
    tournament_context: Mapping[str, object]


class ProposedConstraint(DomainModel):
    key: str = Field(min_length=1, max_length=120)
    classification: Literal["required", "preferred"]
    value: object
    source_text: str = Field(min_length=1, max_length=500)


class ConstraintInterpretationOutput(DomainModel):
    proposed_additions: tuple[ProposedConstraint, ...] = ()
    proposed_changes: tuple[ProposedConstraint, ...] = ()
    ambiguities: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    clarification_question: str | None = Field(default=None, max_length=500)
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)


def validate_constraint_interpretation(
    turn_input: ConstraintInterpretationInput,
    output: ConstraintInterpretationOutput,
) -> ConstraintInterpretationOutput:
    del turn_input
    if (output.ambiguities or output.contradictions) and not output.clarification_question:
        raise ValueError("ambiguous or contradictory intent requires a targeted clarification")
    if output.clarification_question and not output.clarification_question.rstrip().endswith("?"):
        raise ValueError("targeted clarification must be a question")
    return output


_ALLOWED_TOOLS = frozenset(
    {"read_format_rules", "constraint_precheck", "read_location_confirmation"}
)


def create_rules_agent(
    *,
    model: str = "gpt-5.6",
    tools: Sequence[object] = (),
) -> Agent:
    return Agent(
        name="Rules and Constraint Specialist",
        instructions=build_agent_instructions(AgentRole.RULES_CONSTRAINT),
        model=model,
        output_type=ConstraintInterpretationOutput,
        tools=require_allowed_tools(tools, _ALLOWED_TOOLS),
    )
