from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import Field

from app.domain.audit import ActorType, AuditEvent
from app.domain.common import UUID7, DomainModel, UtcDateTime
from app.domain.schedules import DraftStatus


class ApprovalError(ValueError):
    pass


class ApprovalConflict(ApprovalError):
    pass


class ApprovalValidationError(ApprovalError):
    pass


class ApprovalCandidate(DomainModel):
    workspace_id: UUID7
    tournament_id: UUID7
    draft_id: UUID7
    tournament_revision: int = Field(ge=0)
    draft_revision: int = Field(ge=0)
    draft_status: DraftStatus
    validation_valid: bool
    validation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    official_version_id: UUID7 | None
    official_version_number: int = Field(ge=0)
    repair_baseline_version_id: UUID7 | None
    stale: bool


class ApprovalRequest(DomainModel):
    workspace_id: UUID7
    draft_id: UUID7
    expected_revision: int = Field(ge=0)
    expected_official_version_id: UUID7 | None
    confirmation: bool
    idempotency_key: str = Field(min_length=1, max_length=160)
    occurred_at: UtcDateTime


class ApprovedScheduleVersion(DomainModel):
    id: UUID7
    workspace_id: UUID7
    tournament_id: UUID7
    version_number: int = Field(ge=1)
    approved_draft_id: UUID7
    approved_at: UtcDateTime
    supersedes_id: UUID7 | None


class ApprovalRepository(Protocol):
    def transaction(self) -> AbstractContextManager[object]: ...

    def load_candidate(self, workspace_id: UUID, draft_id: UUID) -> ApprovalCandidate | None: ...

    def find_idempotent(self, workspace_id: UUID, key: str) -> ApprovedScheduleVersion | None: ...

    def save_approval(
        self,
        version: ApprovedScheduleVersion,
        audit_event: AuditEvent,
        key: str,
    ) -> None: ...


def _uuid7() -> UUID:
    raw = bytearray(uuid4().bytes)
    raw[6] = (raw[6] & 0x0F) | 0x70
    raw[8] = (raw[8] & 0x3F) | 0x80
    return UUID(bytes=bytes(raw))


class ApprovalService:
    def __init__(self, repository: ApprovalRepository) -> None:
        self._repository = repository

    def approve(self, request: ApprovalRequest) -> ApprovedScheduleVersion:
        if not request.confirmation:
            raise ApprovalValidationError("explicit organizer approval is required")
        with self._repository.transaction():
            replay = self._repository.find_idempotent(request.workspace_id, request.idempotency_key)
            if replay is not None:
                return replay
            candidate = self._repository.load_candidate(request.workspace_id, request.draft_id)
            if candidate is None:
                raise ApprovalConflict("draft is not owned by this workspace")
            self._validate(candidate, request)
            version = ApprovedScheduleVersion(
                id=_uuid7(),
                workspace_id=candidate.workspace_id,
                tournament_id=candidate.tournament_id,
                version_number=candidate.official_version_number + 1,
                approved_draft_id=candidate.draft_id,
                approved_at=request.occurred_at,
                supersedes_id=candidate.official_version_id,
            )
            audit = AuditEvent(
                id=_uuid7(),
                workspace_id=candidate.workspace_id,
                tournament_id=candidate.tournament_id,
                actor_type=ActorType.ORGANIZER,
                event_type="schedule_approved",
                summary=(
                    f"Approved schedule version {version.version_number} as the official "
                    "workspace schedule."
                ),
                structured_payload={
                    "draft_id": str(candidate.draft_id),
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                    "supersedes_id": (
                        str(version.supersedes_id) if version.supersedes_id else None
                    ),
                    "validation_digest": candidate.validation_digest,
                },
                occurred_at=request.occurred_at,
            )
            self._repository.save_approval(version, audit, request.idempotency_key)
            return version

    @staticmethod
    def _validate(candidate: ApprovalCandidate, request: ApprovalRequest) -> None:
        if request.expected_revision != candidate.tournament_revision:
            raise ApprovalConflict("tournament revision is stale")
        if candidate.draft_revision != candidate.tournament_revision:
            raise ApprovalValidationError("draft revision does not match tournament revision")
        if candidate.draft_status is not DraftStatus.READY:
            raise ApprovalValidationError("draft must be ready before approval")
        if not candidate.validation_valid:
            raise ApprovalValidationError("independent validation is required")
        if candidate.stale:
            raise ApprovalValidationError("stale draft cannot be approved")
        if request.expected_official_version_id != candidate.official_version_id:
            raise ApprovalConflict("official schedule changed before approval")
        if (
            candidate.repair_baseline_version_id is not None
            and candidate.repair_baseline_version_id != candidate.official_version_id
        ):
            raise ApprovalConflict("repair baseline is no longer the official schedule")
