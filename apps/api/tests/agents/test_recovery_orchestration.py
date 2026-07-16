from __future__ import annotations

import pytest
from app.agents.orchestration import (
    FlowKind,
    SpecialistInvocation,
    validate_orchestration_sequence,
)
from app.agents.recovery import (
    DisruptionKind,
    RecoveryInput,
    RecoveryOptionEvidence,
    RecoveryOptionExplanation,
    RecoveryOutput,
    validate_recovery_output,
)
from app.agents.schemas import AgentRole, EvidenceRef
from app.domain.schedules import ScheduleDiff
from tests.domain.factories import uuid7


def evidence(kind: str, *fields: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=f"evidence:{kind}",
        evidence_kind=kind,
        revision=4,
        consumed_fields=fields,
    )


def invocation(
    role: AgentRole,
    kind: str,
    *fields: str,
) -> SpecialistInvocation:
    return SpecialistInvocation(
        role=role,
        invocation_reason=f"Use {role.value} evidence in this flow",
        evidence_refs=(evidence(kind, *fields),),
        consumed_by=("director:response",),
    )


@pytest.mark.parametrize(
    ("flow", "invocations"),
    (
        (
            FlowKind.SETUP,
            (
                invocation(
                    AgentRole.RULES_CONSTRAINT,
                    "constraint_precheck",
                    "proposed_delta",
                ),
            ),
        ),
        (
            FlowKind.GENERATION,
            (
                invocation(
                    AgentRole.WEATHER_INTELLIGENCE,
                    "weather_risk_comparison",
                    "coverage",
                    "risk_scores",
                ),
                invocation(
                    AgentRole.SCHEDULING_STRATEGY,
                    "profile_configuration",
                    "profile_requests",
                ),
                invocation(
                    AgentRole.FAIRNESS_LOGISTICS,
                    "fairness_audit",
                    "outliers",
                    "tradeoffs",
                ),
            ),
        ),
        (
            FlowKind.RECOVERY,
            (
                invocation(
                    AgentRole.WEATHER_INTELLIGENCE,
                    "weather_threshold_crossing",
                    "unavailable_slot_ids",
                ),
                invocation(
                    AgentRole.DISRUPTION_RECOVERY,
                    "validated_schedule_diff",
                    "unchanged",
                    "moved",
                    "metric_deltas",
                ),
                invocation(
                    AgentRole.FAIRNESS_LOGISTICS,
                    "repair_fairness_audit",
                    "metric_deltas",
                ),
            ),
        ),
    ),
)
def test_approved_orchestration_sequences_accept_meaningful_evidence(
    flow: FlowKind,
    invocations: tuple[SpecialistInvocation, ...],
) -> None:
    trace = validate_orchestration_sequence(flow, invocations)

    assert trace.flow == flow
    assert trace.invocations == invocations


def test_orchestration_rejects_invocation_whose_output_is_not_consumed() -> None:
    unused = SpecialistInvocation(
        role=AgentRole.RULES_CONSTRAINT,
        invocation_reason="Interpret organizer request",
        evidence_refs=(evidence("constraint_precheck", "proposed_delta"),),
        consumed_by=(),
    )

    with pytest.raises(ValueError, match="ceremonial"):
        validate_orchestration_sequence(FlowKind.SETUP, (unused,))


def test_orchestration_rejects_duplicate_specialist_call() -> None:
    audit = invocation(
        AgentRole.FAIRNESS_LOGISTICS,
        "fairness_audit",
        "outliers",
    )

    with pytest.raises(ValueError, match="duplicate"):
        validate_orchestration_sequence(FlowKind.GENERATION, (audit, audit))


def test_recovery_explanation_must_match_validated_diff() -> None:
    baseline_id = uuid7(1)
    draft_id = uuid7(2)
    moved_id = uuid7(3)
    unchanged_id = uuid7(4)
    diff = ScheduleDiff(
        baseline_version_id=baseline_id,
        draft_id=draft_id,
        unchanged=(unchanged_id,),
        moved=(moved_id,),
        metric_deltas={"weather_risk": -4.0, "group_rest_fairness": 2.0},
    )
    turn_input = RecoveryInput(
        official_version_id=baseline_id,
        disruption_kind=DisruptionKind.RAIN,
        unavailable_slot_ids=(uuid7(5),),
        affected_fixture_ids=(moved_id,),
        validated_repairs=(
            RecoveryOptionEvidence(
                draft_id=draft_id,
                validation_valid=True,
                diff=diff,
            ),
        ),
    )
    output = RecoveryOutput(
        affected_fixture_ids=(moved_id,),
        option_explanations=(
            RecoveryOptionExplanation(
                draft_id=draft_id,
                preserved_count=1,
                moved_count=1,
                added_count=0,
                removed_count=0,
                metric_deltas={"weather_risk": -4.0, "group_rest_fairness": 2.0},
                explanation="Moves one affected fixture and preserves the other fixture.",
            ),
        ),
        recommendation=draft_id,
        evidence_refs=(
            evidence(
                "validated_schedule_diff",
                "unchanged",
                "moved",
                "metric_deltas",
            ),
        ),
    )

    assert validate_recovery_output(turn_input, output) == output


def test_recovery_rejects_fabricated_diff_counts() -> None:
    baseline_id = uuid7(10)
    draft_id = uuid7(11)
    moved_id = uuid7(12)
    turn_input = RecoveryInput(
        official_version_id=baseline_id,
        disruption_kind=DisruptionKind.VENUE_UNAVAILABLE,
        unavailable_slot_ids=(uuid7(13),),
        affected_fixture_ids=(moved_id,),
        validated_repairs=(
            RecoveryOptionEvidence(
                draft_id=draft_id,
                validation_valid=True,
                diff=ScheduleDiff(
                    baseline_version_id=baseline_id,
                    draft_id=draft_id,
                    moved=(moved_id,),
                ),
            ),
        ),
    )
    output = RecoveryOutput(
        affected_fixture_ids=(moved_id,),
        option_explanations=(
            RecoveryOptionExplanation(
                draft_id=draft_id,
                preserved_count=14,
                moved_count=0,
                added_count=0,
                removed_count=0,
                metric_deltas={},
                explanation="No fixture moved.",
            ),
        ),
        evidence_refs=(evidence("validated_schedule_diff", "moved"),),
    )

    with pytest.raises(ValueError, match="validated schedule diff"):
        validate_recovery_output(turn_input, output)


def test_recovery_rejects_invalid_repair_and_preserves_official_baseline() -> None:
    baseline_id = uuid7(20)
    draft_id = uuid7(21)
    turn_input = RecoveryInput(
        official_version_id=baseline_id,
        disruption_kind=DisruptionKind.RAIN,
        unavailable_slot_ids=(uuid7(22),),
        affected_fixture_ids=(uuid7(23),),
        validated_repairs=(
            RecoveryOptionEvidence(
                draft_id=draft_id,
                validation_valid=False,
                diff=ScheduleDiff(
                    baseline_version_id=baseline_id,
                    draft_id=draft_id,
                ),
            ),
        ),
    )
    output = RecoveryOutput(
        affected_fixture_ids=turn_input.affected_fixture_ids,
        option_explanations=(),
        recommendation=None,
        escalation="No valid repair exists; preserve the official schedule.",
        evidence_refs=(evidence("repair_infeasibility", "validation_valid"),),
    )

    assert validate_recovery_output(turn_input, output) == output
