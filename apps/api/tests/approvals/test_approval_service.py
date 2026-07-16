from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import RLock

import pytest
from app.approvals.service import (
    ApprovalCandidate,
    ApprovalConflict,
    ApprovalRequest,
    ApprovalService,
    ApprovalValidationError,
)
from app.domain.schedules import DraftStatus
from tests.domain.factories import uuid7


class MemoryApprovalRepository:
    def __init__(self, candidate: ApprovalCandidate) -> None:
        self.candidate = candidate
        self.versions = []
        self.audit_events = []
        self.idempotency = {}
        self.lock = RLock()

    def transaction(self):
        return self.lock

    def load_candidate(self, workspace_id, draft_id):
        if self.candidate.workspace_id != workspace_id or self.candidate.draft_id != draft_id:
            return None
        return self.candidate

    def find_idempotent(self, workspace_id, key):
        return self.idempotency.get((workspace_id, key))

    def save_approval(self, version, audit_event, key):
        self.versions.append(version)
        self.audit_events.append(audit_event)
        self.idempotency[(version.workspace_id, key)] = version
        self.candidate = self.candidate.model_copy(
            update={
                "draft_status": DraftStatus.APPROVED,
                "official_version_id": version.id,
                "official_version_number": version.version_number,
            }
        )


def candidate() -> ApprovalCandidate:
    return ApprovalCandidate(
        workspace_id=uuid7(1),
        tournament_id=uuid7(2),
        draft_id=uuid7(3),
        tournament_revision=4,
        draft_revision=4,
        draft_status=DraftStatus.READY,
        validation_valid=True,
        validation_digest="a" * 64,
        official_version_id=None,
        official_version_number=0,
        repair_baseline_version_id=None,
        stale=False,
    )


def request(source: ApprovalCandidate, *, key: str = "approve-1") -> ApprovalRequest:
    return ApprovalRequest(
        workspace_id=source.workspace_id,
        draft_id=source.draft_id,
        expected_revision=source.tournament_revision,
        expected_official_version_id=source.official_version_id,
        confirmation=True,
        idempotency_key=key,
        occurred_at=datetime(2026, 7, 16, 12, tzinfo=UTC),
    )


def test_explicit_approval_creates_version_and_audit_atomically() -> None:
    source = candidate()
    repository = MemoryApprovalRepository(source)

    result = ApprovalService(repository).approve(request(source))

    assert result.version_number == 1
    assert result.approved_draft_id == source.draft_id
    assert result.supersedes_id is None
    assert len(repository.versions) == 1
    assert repository.audit_events[0].event_type == "schedule_approved"
    assert repository.audit_events[0].structured_payload["validation_digest"] == "a" * 64


def test_concurrent_idempotent_approval_creates_only_one_version() -> None:
    source = candidate()
    repository = MemoryApprovalRepository(source)
    service = ApprovalService(repository)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: service.approve(request(source)), range(2)))

    assert results[0] == results[1]
    assert len(repository.versions) == 1
    assert len(repository.audit_events) == 1


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        ({"draft_status": DraftStatus.INVALID}, "ready"),
        ({"validation_valid": False}, "validation"),
        ({"stale": True}, "stale"),
        ({"draft_revision": 3}, "revision"),
    ),
)
def test_invalid_stale_or_unready_draft_is_rejected(updates, message) -> None:
    source = candidate().model_copy(update=updates)

    with pytest.raises(ApprovalValidationError, match=message):
        ApprovalService(MemoryApprovalRepository(source)).approve(request(source))


def test_repair_requires_current_official_baseline() -> None:
    current = uuid7(8)
    source = candidate().model_copy(
        update={
            "official_version_id": current,
            "official_version_number": 2,
            "repair_baseline_version_id": uuid7(9),
        }
    )

    with pytest.raises(ApprovalConflict, match="baseline"):
        ApprovalService(MemoryApprovalRepository(source)).approve(request(source))


def test_conversation_or_missing_confirmation_cannot_approve() -> None:
    source = candidate()
    unconfirmed = request(source).model_copy(update={"confirmation": False})

    with pytest.raises(ApprovalValidationError, match="explicit"):
        ApprovalService(MemoryApprovalRepository(source)).approve(unconfirmed)
