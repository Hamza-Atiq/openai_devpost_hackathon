from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from app.workspaces.service import (
    GuestWorkspaceRecord,
    WorkspaceDeleted,
    WorkspaceExpired,
    WorkspaceOwnershipError,
    WorkspaceService,
)
from tests.domain.factories import uuid7

NOW = datetime(2026, 7, 16, 12, tzinfo=UTC)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class MemoryWorkspaceRepository:
    def __init__(self, records):
        self.records = {record.token_hash: record for record in records}
        self.reset_calls = []
        self.hard_deleted = []

    def find_by_token_hash(self, token_hash):
        return self.records.get(token_hash)

    def save(self, record):
        self.records[record.token_hash] = record

    def reset_tournament(self, workspace_id, sample_id):
        self.reset_calls.append((workspace_id, sample_id))

    def expired_before(self, now):
        return tuple(
            item for item in self.records.values() if not item.deleted and item.expires_at <= now
        )

    def pending_hard_delete(self, now):
        return tuple(
            item
            for item in self.records.values()
            if item.deleted and item.hard_delete_after is not None and item.hard_delete_after <= now
        )

    def hard_delete(self, workspace_id):
        self.hard_deleted.append(workspace_id)
        self.records = {
            token: record for token, record in self.records.items() if record.id != workspace_id
        }


def record(number: int, token_hash: str) -> GuestWorkspaceRecord:
    return GuestWorkspaceRecord(
        id=uuid7(number),
        token_hash=token_hash,
        last_active_at=NOW,
        expires_at=NOW + timedelta(days=7),
        deleted=False,
        deleted_at=None,
        hard_delete_after=None,
    )


def test_authenticated_request_extends_seven_day_expiration() -> None:
    source = record(1, token_hash("guest-a"))
    repository = MemoryWorkspaceRepository((source,))

    restored = WorkspaceService(repository).restore(
        "guest-a", source.id, now=NOW + timedelta(days=2)
    )

    assert restored.last_active_at == NOW + timedelta(days=2)
    assert restored.expires_at == NOW + timedelta(days=9)


def test_identifier_manipulation_cannot_cross_guest_boundary() -> None:
    first = record(1, token_hash("guest-a"))
    second = record(2, token_hash("guest-b"))
    service = WorkspaceService(MemoryWorkspaceRepository((first, second)))

    with pytest.raises(WorkspaceOwnershipError):
        service.restore("guest-a", second.id, now=NOW)


def test_expired_or_deleted_workspace_cannot_be_restored() -> None:
    expired = record(1, token_hash("guest-a")).model_copy(update={"expires_at": NOW})
    deleted = record(2, token_hash("guest-b")).model_copy(
        update={"deleted": True, "deleted_at": NOW}
    )
    service = WorkspaceService(MemoryWorkspaceRepository((expired, deleted)))

    with pytest.raises(WorkspaceExpired):
        service.restore("guest-a", expired.id, now=NOW)
    with pytest.raises(WorkspaceDeleted):
        service.restore("guest-b", deleted.id, now=NOW)


def test_reset_keeps_workspace_but_replaces_tournament_data() -> None:
    source = record(1, token_hash("guest-a"))
    repository = MemoryWorkspaceRepository((source,))

    restored = WorkspaceService(repository).reset(
        "guest-a", source.id, sample_id="pakistan-community-cup", now=NOW
    )

    assert restored.id == source.id
    assert repository.reset_calls == [(source.id, "pakistan-community-cup")]


def test_delete_is_immediate_and_hard_delete_is_due_within_fifteen_minutes() -> None:
    source = record(1, token_hash("guest-a"))
    repository = MemoryWorkspaceRepository((source,))
    service = WorkspaceService(repository)

    deleted = service.delete("guest-a", source.id, confirmation=True, now=NOW)
    service.cleanup(now=NOW + timedelta(minutes=15))

    assert deleted.deleted is True
    assert deleted.hard_delete_after == NOW + timedelta(minutes=15)
    assert repository.hard_deleted == [source.id]


def test_daily_cleanup_marks_inactive_workspace_deleted_then_purges() -> None:
    source = record(1, token_hash("guest-a")).model_copy(update={"expires_at": NOW})
    repository = MemoryWorkspaceRepository((source,))
    service = WorkspaceService(repository)

    result = service.cleanup(now=NOW)

    assert result.marked_deleted == 1
    assert repository.records[source.token_hash].hard_delete_after == NOW + timedelta(hours=24)
