from __future__ import annotations

import pytest
from app.domain.schedules import DraftStatus, ValidationReport
from app.domain.states import (
    ForbiddenTransitionError,
    StaleRevisionError,
    TraceabilityError,
    TransitionCommand,
    TransitionContext,
    ValidationRequiredError,
    allowed_draft_transitions,
    allowed_tournament_transitions,
    transition_draft,
    transition_tournament,
)
from app.domain.tournament import TournamentStatus
from tests.domain.factories import uuid7


def context(
    command: TransitionCommand, *, revision: int = 4, draft: bool = False
) -> TransitionContext:
    return TransitionContext(
        expected_revision=revision,
        actual_revision=revision,
        command=command,
        audit_event_id=uuid7(900),
        draft_id=uuid7(901) if draft else None,
    )


TOURNAMENT_COMMANDS = {
    (
        TournamentStatus.DRAFT_SETUP,
        TournamentStatus.AWAITING_CONSTRAINT_CONFIRMATION,
    ): TransitionCommand.SYSTEM,
    (
        TournamentStatus.AWAITING_CONSTRAINT_CONFIRMATION,
        TournamentStatus.READY_TO_SCHEDULE,
    ): TransitionCommand.CONFIRM_CONSTRAINTS,
    (TournamentStatus.READY_TO_SCHEDULE, TournamentStatus.OPTIONS_READY): TransitionCommand.SYSTEM,
    (
        TournamentStatus.OPTIONS_READY,
        TournamentStatus.OFFICIAL_SCHEDULE,
    ): TransitionCommand.APPROVE_SCHEDULE,
    (TournamentStatus.OFFICIAL_SCHEDULE, TournamentStatus.RECOVERY_DRAFT): TransitionCommand.SYSTEM,
    (
        TournamentStatus.RECOVERY_DRAFT,
        TournamentStatus.OFFICIAL_SCHEDULE,
    ): TransitionCommand.APPROVE_REPAIR,
}


def test_tournament_transition_table_is_exhaustive() -> None:
    assert allowed_tournament_transitions() == frozenset(TOURNAMENT_COMMANDS)

    for current in TournamentStatus:
        for target in TournamentStatus:
            command = TOURNAMENT_COMMANDS.get((current, target))
            if command is None:
                with pytest.raises(ForbiddenTransitionError):
                    transition_tournament(current, target, context(TransitionCommand.SYSTEM))
            else:
                result = transition_tournament(
                    current,
                    target,
                    context(
                        command,
                        draft=command
                        in {TransitionCommand.APPROVE_SCHEDULE, TransitionCommand.APPROVE_REPAIR},
                    ),
                )
                assert result.current_state == target
                assert result.revision == 5


def test_direct_draft_to_official_and_conversational_approval_fail() -> None:
    with pytest.raises(ForbiddenTransitionError):
        transition_tournament(
            TournamentStatus.DRAFT_SETUP,
            TournamentStatus.OFFICIAL_SCHEDULE,
            context(TransitionCommand.APPROVE_SCHEDULE, draft=True),
        )

    with pytest.raises(ForbiddenTransitionError, match="explicit command"):
        transition_tournament(
            TournamentStatus.OPTIONS_READY,
            TournamentStatus.OFFICIAL_SCHEDULE,
            context(TransitionCommand.CONVERSATION, draft=True),
        )


def test_stale_revision_and_untraceable_approval_fail() -> None:
    stale = context(TransitionCommand.APPROVE_SCHEDULE, draft=True).model_copy(
        update={"expected_revision": 3}
    )
    with pytest.raises(StaleRevisionError):
        transition_tournament(
            TournamentStatus.OPTIONS_READY,
            TournamentStatus.OFFICIAL_SCHEDULE,
            stale,
        )

    with pytest.raises(TraceabilityError, match="draft_id"):
        transition_tournament(
            TournamentStatus.OPTIONS_READY,
            TournamentStatus.OFFICIAL_SCHEDULE,
            context(TransitionCommand.APPROVE_SCHEDULE),
        )


DRAFT_COMMANDS = {
    (DraftStatus.QUEUED, DraftStatus.SOLVING): TransitionCommand.SYSTEM,
    (DraftStatus.SOLVING, DraftStatus.VALIDATING): TransitionCommand.SYSTEM,
    (DraftStatus.SOLVING, DraftStatus.INFEASIBLE): TransitionCommand.SYSTEM,
    (DraftStatus.SOLVING, DraftStatus.FAILED): TransitionCommand.SYSTEM,
    (DraftStatus.SOLVING, DraftStatus.CANCELLED): TransitionCommand.CANCEL_DRAFT,
    (DraftStatus.VALIDATING, DraftStatus.READY): TransitionCommand.SYSTEM,
    (DraftStatus.VALIDATING, DraftStatus.INVALID): TransitionCommand.SYSTEM,
    (DraftStatus.READY, DraftStatus.APPROVED): TransitionCommand.APPROVE_SCHEDULE,
    (DraftStatus.READY, DraftStatus.REJECTED): TransitionCommand.REJECT_DRAFT,
    (DraftStatus.READY, DraftStatus.SUPERSEDED): TransitionCommand.SYSTEM,
}


def test_draft_transition_table_is_exhaustive() -> None:
    assert allowed_draft_transitions() == frozenset(DRAFT_COMMANDS)

    for current in DraftStatus:
        for target in DraftStatus:
            command = DRAFT_COMMANDS.get((current, target))
            if command is None:
                with pytest.raises(ForbiddenTransitionError):
                    transition_draft(current, target, context(TransitionCommand.SYSTEM))
            else:
                report = None
                if (current, target) == (DraftStatus.VALIDATING, DraftStatus.READY):
                    report = ValidationReport(valid=True)
                elif (current, target) == (DraftStatus.VALIDATING, DraftStatus.INVALID):
                    report = ValidationReport(valid=False, violations=("seeded",))
                transition_context = context(
                    command,
                    draft=target is DraftStatus.APPROVED,
                )
                result = transition_draft(current, target, transition_context, report)
                assert result.current_state == target
                assert result.revision == 4


def test_ready_requires_valid_independent_report() -> None:
    with pytest.raises(ValidationRequiredError):
        transition_draft(
            DraftStatus.VALIDATING,
            DraftStatus.READY,
            context(TransitionCommand.SYSTEM),
            ValidationReport(valid=False, violations=("overlap",)),
        )


def test_draft_approval_requires_explicit_command_and_draft_identity() -> None:
    with pytest.raises(ForbiddenTransitionError, match="explicit command"):
        transition_draft(
            DraftStatus.READY,
            DraftStatus.APPROVED,
            context(TransitionCommand.CONVERSATION, draft=True),
        )
    with pytest.raises(TraceabilityError, match="draft_id"):
        transition_draft(
            DraftStatus.READY,
            DraftStatus.APPROVED,
            context(TransitionCommand.APPROVE_SCHEDULE),
        )
