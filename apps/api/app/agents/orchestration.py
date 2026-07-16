from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from pydantic import Field

from app.agents.schemas import AgentRole, EvidenceRef
from app.domain.common import DomainModel


class FlowKind(StrEnum):
    SETUP = "setup"
    GENERATION = "generation"
    RECOVERY = "recovery"


class SpecialistInvocation(DomainModel):
    role: AgentRole
    invocation_reason: str = Field(min_length=1, max_length=500)
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)
    consumed_by: tuple[str, ...]


class OrchestrationTrace(DomainModel):
    flow: FlowKind
    invocations: tuple[SpecialistInvocation, ...]


_ROLE_EVIDENCE_KINDS: dict[AgentRole, frozenset[str]] = {
    AgentRole.RULES_CONSTRAINT: frozenset({"constraint_precheck"}),
    AgentRole.SCHEDULING_STRATEGY: frozenset({"profile_configuration"}),
    AgentRole.WEATHER_INTELLIGENCE: frozenset(
        {"weather_risk_comparison", "weather_threshold_crossing"}
    ),
    AgentRole.FAIRNESS_LOGISTICS: frozenset({"fairness_audit", "repair_fairness_audit"}),
    AgentRole.DISRUPTION_RECOVERY: frozenset({"validated_schedule_diff", "repair_infeasibility"}),
}


def _validate_roles(flow: FlowKind, roles: tuple[AgentRole, ...]) -> None:
    if len(set(roles)) != len(roles):
        raise ValueError("duplicate specialist invocation is not meaningful")
    if flow is FlowKind.SETUP and roles != (AgentRole.RULES_CONSTRAINT,):
        raise ValueError("setup flow must invoke only the Rules specialist")
    if flow is FlowKind.GENERATION:
        if (
            set(roles)
            != {
                AgentRole.SCHEDULING_STRATEGY,
                AgentRole.WEATHER_INTELLIGENCE,
                AgentRole.FAIRNESS_LOGISTICS,
            }
            or roles[-1] is not AgentRole.FAIRNESS_LOGISTICS
        ):
            raise ValueError(
                "generation requires Strategy and Weather preparation before Fairness audit"
            )
    if flow is FlowKind.RECOVERY:
        required = (AgentRole.DISRUPTION_RECOVERY, AgentRole.FAIRNESS_LOGISTICS)
        if roles == required:
            return
        if roles != (AgentRole.WEATHER_INTELLIGENCE, *required):
            raise ValueError(
                "recovery requires Recovery then Fairness, with Weather first only for rain"
            )


def validate_orchestration_sequence(
    flow: FlowKind,
    invocations: Sequence[SpecialistInvocation],
) -> OrchestrationTrace:
    invocations = tuple(invocations)
    _validate_roles(flow, tuple(item.role for item in invocations))
    for item in invocations:
        allowed_kinds = _ROLE_EVIDENCE_KINDS.get(item.role, frozenset())
        if not item.consumed_by:
            raise ValueError("ceremonial specialist invocation has no consumed output")
        if not any(
            ref.evidence_kind in allowed_kinds and ref.consumed_fields for ref in item.evidence_refs
        ):
            raise ValueError(f"{item.role.value} invocation consumed no role-specific evidence")
    return OrchestrationTrace(flow=flow, invocations=invocations)
