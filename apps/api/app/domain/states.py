from __future__ import annotations

from enum import StrEnum

from app.domain.common import UUID7, DomainModel
from app.domain.schedules import DraftStatus, ValidationReport
from app.domain.tournament import TournamentStatus


class DomainTransitionError(ValueError):
    """Base error for rejected authoritative state changes."""


class ForbiddenTransitionError(DomainTransitionError):
    """Raised when the state edge or command is not authorized."""


class StaleRevisionError(DomainTransitionError):
    """Raised when a command targets an outdated tournament revision."""


class TraceabilityError(DomainTransitionError):
    """Raised when the transition lacks required audit or draft identity."""


class ValidationRequiredError(DomainTransitionError):
    """Raised when a ready/invalid decision lacks matching validation evidence."""


class TransitionCommand(StrEnum):
    SYSTEM = "system"
    CONVERSATION = "conversation"
    CONFIRM_CONSTRAINTS = "confirm_constraints"
    APPROVE_SCHEDULE = "approve_schedule"
    APPROVE_REPAIR = "approve_repair"
    REJECT_DRAFT = "reject_draft"
    CANCEL_DRAFT = "cancel_draft"


class TransitionContext(DomainModel):
    expected_revision: int
    actual_revision: int
    command: TransitionCommand
    audit_event_id: UUID7
    draft_id: UUID7 | None = None


class StateTransition(DomainModel):
    previous_state: TournamentStatus | DraftStatus
    current_state: TournamentStatus | DraftStatus
    revision: int
    audit_event_id: UUID7
    draft_id: UUID7 | None = None


_TOURNAMENT_COMMANDS: dict[
    tuple[TournamentStatus, TournamentStatus], TransitionCommand
] = {
    (
        TournamentStatus.DRAFT_SETUP,
        TournamentStatus.AWAITING_CONSTRAINT_CONFIRMATION,
    ): TransitionCommand.SYSTEM,
    (
        TournamentStatus.AWAITING_CONSTRAINT_CONFIRMATION,
        TournamentStatus.READY_TO_SCHEDULE,
    ): TransitionCommand.CONFIRM_CONSTRAINTS,
    (
        TournamentStatus.READY_TO_SCHEDULE,
        TournamentStatus.OPTIONS_READY,
    ): TransitionCommand.SYSTEM,
    (
        TournamentStatus.OPTIONS_READY,
        TournamentStatus.OFFICIAL_SCHEDULE,
    ): TransitionCommand.APPROVE_SCHEDULE,
    (
        TournamentStatus.OFFICIAL_SCHEDULE,
        TournamentStatus.RECOVERY_DRAFT,
    ): TransitionCommand.SYSTEM,
    (
        TournamentStatus.RECOVERY_DRAFT,
        TournamentStatus.OFFICIAL_SCHEDULE,
    ): TransitionCommand.APPROVE_REPAIR,
}

_DRAFT_COMMANDS: dict[tuple[DraftStatus, DraftStatus], TransitionCommand] = {
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


def allowed_tournament_transitions() -> frozenset[tuple[TournamentStatus, TournamentStatus]]:
    return frozenset(_TOURNAMENT_COMMANDS)


def allowed_draft_transitions() -> frozenset[tuple[DraftStatus, DraftStatus]]:
    return frozenset(_DRAFT_COMMANDS)


def _validate_context(context: TransitionContext) -> None:
    if context.expected_revision != context.actual_revision:
        raise StaleRevisionError(
            f"expected revision {context.expected_revision}, current revision "
            f"is {context.actual_revision}"
        )
    if context.audit_event_id is None:
        raise TraceabilityError("audit_event_id is required")


def _require_command(
    required: TransitionCommand,
    context: TransitionContext,
    *,
    allowed_alternative: TransitionCommand | None = None,
) -> None:
    accepted = {required}
    if allowed_alternative is not None:
        accepted.add(allowed_alternative)
    if context.command not in accepted:
        raise ForbiddenTransitionError(
            f"transition requires explicit command: {required.value}"
        )


def _require_draft_identity(context: TransitionContext) -> None:
    if context.draft_id is None:
        raise TraceabilityError("draft_id is required for schedule approval")


def transition_tournament(
    current: TournamentStatus,
    target: TournamentStatus,
    context: TransitionContext,
) -> StateTransition:
    _validate_context(context)
    required_command = _TOURNAMENT_COMMANDS.get((current, target))
    if required_command is None:
        raise ForbiddenTransitionError(f"forbidden tournament transition: {current} -> {target}")
    _require_command(required_command, context)
    if target is TournamentStatus.OFFICIAL_SCHEDULE:
        _require_draft_identity(context)
    return StateTransition(
        previous_state=current,
        current_state=target,
        revision=context.actual_revision + 1,
        audit_event_id=context.audit_event_id,
        draft_id=context.draft_id,
    )


def transition_draft(
    current: DraftStatus,
    target: DraftStatus,
    context: TransitionContext,
    validation_report: ValidationReport | None = None,
) -> StateTransition:
    _validate_context(context)
    required_command = _DRAFT_COMMANDS.get((current, target))
    if required_command is None:
        raise ForbiddenTransitionError(f"forbidden draft transition: {current} -> {target}")
    alternative = (
        TransitionCommand.APPROVE_REPAIR
        if (current, target) == (DraftStatus.READY, DraftStatus.APPROVED)
        else None
    )
    _require_command(required_command, context, allowed_alternative=alternative)
    if (current, target) == (DraftStatus.VALIDATING, DraftStatus.READY):
        if validation_report is None or not validation_report.valid:
            raise ValidationRequiredError("ready requires a valid independent report")
    if (current, target) == (DraftStatus.VALIDATING, DraftStatus.INVALID):
        if validation_report is None or validation_report.valid:
            raise ValidationRequiredError("invalid requires a failing independent report")
    if target is DraftStatus.APPROVED:
        _require_draft_identity(context)
    return StateTransition(
        previous_state=current,
        current_state=target,
        revision=context.actual_revision,
        audit_event_id=context.audit_event_id,
        draft_id=context.draft_id,
    )
