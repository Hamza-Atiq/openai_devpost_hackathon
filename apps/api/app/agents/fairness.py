from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Literal

from agents import Agent
from pydantic import Field

from app.agents.instructions import build_agent_instructions
from app.agents.schemas import AgentRole, EvidenceRef
from app.agents.specialist_tools import require_allowed_tools
from app.domain.common import DomainModel

FAIRNESS_BOUNDARY = "This is a schedule-derived comparison, not a universal definition of fairness."


class FairnessAuditInput(DomainModel):
    schedule_id: str = Field(min_length=1, max_length=240)
    validation_valid: bool
    metric_version: str = Field(min_length=1, max_length=120)
    metrics: Mapping[str, float]
    team_breakdown: Mapping[str, Mapping[str, float]]


class FairnessOutlier(DomainModel):
    team_id: str = Field(min_length=1, max_length=160)
    metric: str = Field(min_length=1, max_length=120)
    value: float
    reason: str = Field(min_length=1, max_length=500)


class FairnessAuditOutput(DomainModel):
    findings: tuple[str, ...]
    outliers: tuple[FairnessOutlier, ...] = ()
    tradeoffs: tuple[str, ...] = ()
    group_rest_summary: str = Field(min_length=1, max_length=1000)
    potential_knockout_rest_summary: str = Field(min_length=1, max_length=1000)
    metric_claims: Mapping[str, float]
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)
    overall_summary: str = Field(min_length=1, max_length=1200)
    fairness_boundary: Literal[
        "This is a schedule-derived comparison, not a universal definition of fairness."
    ] = FAIRNESS_BOUNDARY


_PLACEHOLDER_OVERCOUNT = re.compile(
    r"every (?:qualification )?placeholder (?:is|counts as) an? actual appearance",
    re.IGNORECASE,
)


def validate_fairness_audit(
    turn_input: FairnessAuditInput,
    output: FairnessAuditOutput,
) -> FairnessAuditOutput:
    if not turn_input.validation_valid:
        raise ValueError("fairness explanation requires an independently validated schedule")
    if turn_input.metric_version != "schedule-metrics/v1":
        raise ValueError("fairness metric version mismatch")
    if any(
        name not in turn_input.metrics or turn_input.metrics[name] != value
        for name, value in output.metric_claims.items()
    ):
        raise ValueError("fairness output contains a fabricated fairness metric")
    if any(outlier.team_id not in turn_input.team_breakdown for outlier in output.outliers):
        raise ValueError("fairness output contains an unknown team outlier")
    if _PLACEHOLDER_OVERCOUNT.search(output.potential_knockout_rest_summary):
        raise ValueError("qualification placeholders cannot be counted as actual appearances")
    return output


_ALLOWED_TOOLS = frozenset({"read_validated_metrics", "read_fixture_breakdown"})


def create_fairness_agent(
    *,
    model: str = "gpt-5.6",
    tools: Sequence[object] = (),
) -> Agent:
    return Agent(
        name="Fairness and Logistics Auditor",
        instructions=build_agent_instructions(AgentRole.FAIRNESS_LOGISTICS),
        model=model,
        output_type=FairnessAuditOutput,
        tools=require_allowed_tools(tools, _ALLOWED_TOOLS),
    )
