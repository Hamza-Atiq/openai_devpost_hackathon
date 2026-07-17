from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from agents import Agent
from pydantic import Field

from app.agents.instructions import build_agent_instructions
from app.agents.schemas import AgentRole, EvidenceRef
from app.agents.specialist_tools import require_allowed_tools
from app.domain.common import UUID7, DomainModel
from app.domain.schedules import ScheduleDiff


class DisruptionKind(StrEnum):
    RAIN = "rain"
    VENUE_UNAVAILABLE = "venue_unavailable"


class RecoveryOptionEvidence(DomainModel):
    draft_id: UUID7
    validation_valid: bool
    diff: ScheduleDiff


class RecoveryMetricDeltas(DomainModel):
    weather_risk: float | None = None
    weather_coverage: float | None = None
    missing_coverage_penalty: float | None = None
    group_rest_fairness: float | None = None
    potential_knockout_rest: float | None = None
    venue_balance: float | None = None
    slot_balance: float | None = None
    preference_satisfaction: float | None = None
    change_cost: float | None = None


class RecoveryInput(DomainModel):
    official_version_id: UUID7
    disruption_kind: DisruptionKind
    unavailable_slot_ids: tuple[UUID7, ...] = Field(min_length=1)
    affected_fixture_ids: tuple[UUID7, ...]
    validated_repairs: tuple[RecoveryOptionEvidence, ...] = ()


class RecoveryOptionExplanation(DomainModel):
    draft_id: UUID7
    preserved_count: int = Field(ge=0)
    moved_count: int = Field(ge=0)
    added_count: int = Field(ge=0)
    removed_count: int = Field(ge=0)
    metric_deltas: RecoveryMetricDeltas
    explanation: str = Field(min_length=1, max_length=1200)


class RecoveryOutput(DomainModel):
    affected_fixture_ids: tuple[UUID7, ...]
    option_explanations: tuple[RecoveryOptionExplanation, ...] = ()
    recommendation: UUID7 | None = None
    escalation: str | None = Field(default=None, max_length=1200)
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)


def _matches_diff(
    explanation: RecoveryOptionExplanation,
    diff: ScheduleDiff,
) -> bool:
    return (
        explanation.preserved_count == len(diff.unchanged)
        and explanation.moved_count == len(diff.moved)
        and explanation.added_count == len(diff.added)
        and explanation.removed_count == len(diff.removed)
        and explanation.metric_deltas.model_dump(
            exclude={"schema_version"}, exclude_none=True
        )
        == dict(diff.metric_deltas)
    )


def validate_recovery_output(
    turn_input: RecoveryInput,
    output: RecoveryOutput,
) -> RecoveryOutput:
    if set(output.affected_fixture_ids) != set(turn_input.affected_fixture_ids):
        raise ValueError("recovery output changed the deterministically affected fixtures")
    repairs = {repair.draft_id: repair for repair in turn_input.validated_repairs}
    valid_repairs = {
        draft_id: repair for draft_id, repair in repairs.items() if repair.validation_valid
    }
    for repair in repairs.values():
        if repair.diff.baseline_version_id != turn_input.official_version_id:
            raise ValueError("repair diff does not use the latest official baseline")
        if repair.diff.draft_id != repair.draft_id:
            raise ValueError("repair evidence references a mismatched draft")
    for explanation in output.option_explanations:
        repair = valid_repairs.get(explanation.draft_id)
        if repair is None or not _matches_diff(explanation, repair.diff):
            raise ValueError("recovery explanation does not match the validated schedule diff")
    if output.recommendation is not None:
        if output.recommendation not in valid_repairs:
            raise ValueError("recovery recommendation must reference a validated repair")
        if not any(ref.evidence_kind == "validated_schedule_diff" for ref in output.evidence_refs):
            raise ValueError("recovery recommendation requires validated schedule diff evidence")
    if not valid_repairs:
        if output.option_explanations or output.recommendation is not None:
            raise ValueError("an invalid repair cannot be presented or recommended")
        if not output.escalation:
            raise ValueError("infeasible recovery must preserve the baseline and escalate")
    return output


_ALLOWED_TOOLS = frozenset(
    {
        "analyze_affected_slots",
        "start_deterministic_repair",
        "read_validated_schedule_diff",
        "read_repair_metrics",
    }
)


def create_recovery_agent(
    *,
    model: str = "gpt-5.6",
    tools: Sequence[object] = (),
) -> Agent:
    return Agent(
        name="Disruption and Recovery Specialist",
        instructions=build_agent_instructions(AgentRole.DISRUPTION_RECOVERY),
        model=model,
        output_type=RecoveryOutput,
        tools=require_allowed_tools(tools, _ALLOWED_TOOLS),
    )
