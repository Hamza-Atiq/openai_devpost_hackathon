from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from pydantic import Field

from app.domain.common import UUID7, DomainModel, UtcDateTime


class WorkspaceError(ValueError):
    pass


class WorkspaceOwnershipError(WorkspaceError):
    pass


class WorkspaceExpired(WorkspaceError):
    pass


class WorkspaceDeleted(WorkspaceError):
    pass


class GuestWorkspaceRecord(DomainModel):
    id: UUID7
    token_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    last_active_at: UtcDateTime
    expires_at: UtcDateTime
    deleted: bool
    deleted_at: UtcDateTime | None
    hard_delete_after: UtcDateTime | None


class CleanupResult(DomainModel):
    marked_deleted: int = Field(ge=0)
    hard_deleted: int = Field(ge=0)


class WorkspaceRepository(Protocol):
    def find_by_token_hash(self, token_hash: str) -> GuestWorkspaceRecord | None: ...

    def save(self, record: GuestWorkspaceRecord) -> None: ...

    def reset_tournament(self, workspace_id: UUID, sample_id: str | None) -> None: ...

    def expired_before(self, now: UtcDateTime) -> tuple[GuestWorkspaceRecord, ...]: ...

    def pending_hard_delete(self, now: UtcDateTime) -> tuple[GuestWorkspaceRecord, ...]: ...

    def hard_delete(self, workspace_id: UUID) -> None: ...


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository) -> None:
        self._repository = repository

    def _owned(
        self,
        token: str,
        requested_workspace_id: UUID,
        *,
        now: UtcDateTime,
        touch: bool,
    ) -> GuestWorkspaceRecord:
        workspace = self._repository.find_by_token_hash(_hash_token(token))
        if workspace is None or workspace.id != requested_workspace_id:
            raise WorkspaceOwnershipError("workspace does not belong to this guest")
        if workspace.deleted:
            raise WorkspaceDeleted("workspace has been deleted")
        if workspace.expires_at <= now:
            raise WorkspaceExpired("workspace has expired")
        if touch:
            workspace = workspace.model_copy(
                update={
                    "last_active_at": now,
                    "expires_at": now + timedelta(days=7),
                }
            )
            self._repository.save(workspace)
        return workspace

    def restore(
        self,
        token: str,
        requested_workspace_id: UUID,
        *,
        now: UtcDateTime,
    ) -> GuestWorkspaceRecord:
        return self._owned(token, requested_workspace_id, now=now, touch=True)

    def reset(
        self,
        token: str,
        requested_workspace_id: UUID,
        *,
        sample_id: str | None,
        now: UtcDateTime,
    ) -> GuestWorkspaceRecord:
        workspace = self._owned(token, requested_workspace_id, now=now, touch=True)
        self._repository.reset_tournament(workspace.id, sample_id)
        return workspace

    def delete(
        self,
        token: str,
        requested_workspace_id: UUID,
        *,
        confirmation: bool,
        now: UtcDateTime,
    ) -> GuestWorkspaceRecord:
        if not confirmation:
            raise WorkspaceError("explicit deletion confirmation is required")
        workspace = self._owned(token, requested_workspace_id, now=now, touch=False)
        deleted = workspace.model_copy(
            update={
                "deleted": True,
                "deleted_at": now,
                "hard_delete_after": now + timedelta(minutes=15),
            }
        )
        self._repository.save(deleted)
        return deleted

    def cleanup(self, *, now: UtcDateTime) -> CleanupResult:
        expired = self._repository.expired_before(now)
        for workspace in expired:
            self._repository.save(
                workspace.model_copy(
                    update={
                        "deleted": True,
                        "deleted_at": now,
                        "hard_delete_after": now + timedelta(hours=24),
                    }
                )
            )
        pending = self._repository.pending_hard_delete(now)
        for workspace in pending:
            self._repository.hard_delete(workspace.id)
        return CleanupResult(marked_deleted=len(expired), hard_deleted=len(pending))
