from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.domain.tournament import TournamentConfig
from app.persistence.models import GuestWorkspace as PersistedWorkspace
from app.persistence.models import WorkspaceSnapshot
from app.scheduling.profiles import GeneratedProfileOption


@dataclass(slots=True)
class GuestWorkspace:
    workspace_id: str
    tournament: TournamentConfig | None
    csrf_token: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    weather: dict[str, Any] = field(
        default_factory=lambda: {
            "mode": "live",
            "quality": "not_requested",
            "demo_mode_available": True,
            "scenario_id": None,
        }
    )
    schedule_runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    drafts: dict[str, Any] = field(default_factory=dict)
    draft_revisions: dict[str, int] = field(default_factory=dict)
    rejected_drafts: set[str] = field(default_factory=set)
    idempotency: dict[str, dict[str, object]] = field(default_factory=dict)
    official_versions: list[dict[str, object]] = field(default_factory=list)
    edits: dict[str, dict[str, object]] = field(default_factory=dict)
    disruptions: dict[str, dict[str, object]] = field(default_factory=dict)
    schedule_diffs: dict[str, dict[str, object]] = field(default_factory=dict)
    feedback: list[dict[str, object]] = field(default_factory=list)
    constraint_confirmation: dict[str, object] | None = None
    audit_events: list[dict[str, Any]] = field(default_factory=list)


class GuestWorkspaceStore:
    def __init__(self) -> None:
        self._items: dict[str, GuestWorkspace] = {}

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, tournament: TournamentConfig | None) -> tuple[str, GuestWorkspace]:
        token = secrets.token_urlsafe(32)
        workspace = GuestWorkspace(workspace_id=str(uuid4()), tournament=tournament)
        self._items[self._digest(token)] = workspace
        return token, workspace

    def get(self, token: str | None) -> GuestWorkspace | None:
        if not token:
            return None
        return self._items.get(self._digest(token))

    def delete(self, token: str) -> None:
        self._items.pop(self._digest(token), None)

    def persist(self, token: str | None) -> None:
        """Persist a mutated workspace when the configured store is durable."""

    def cached(self, token: str | None) -> GuestWorkspace | None:
        return self._items.get(self._digest(token)) if token else None


def _workspace_payload(workspace: GuestWorkspace) -> dict[str, Any]:
    return jsonable_encoder(
        {
            "tournament": workspace.tournament,
            "csrf_token": workspace.csrf_token,
            "weather": workspace.weather,
            "schedule_runs": workspace.schedule_runs,
            "drafts": workspace.drafts,
            "draft_revisions": workspace.draft_revisions,
            "rejected_drafts": sorted(workspace.rejected_drafts),
            "idempotency": workspace.idempotency,
            "official_versions": workspace.official_versions,
            "edits": workspace.edits,
            "disruptions": workspace.disruptions,
            "schedule_diffs": workspace.schedule_diffs,
            "feedback": workspace.feedback,
            "constraint_confirmation": workspace.constraint_confirmation,
            "audit_events": workspace.audit_events,
        }
    )


def _workspace_from_payload(workspace_id: str, payload: dict[str, Any]) -> GuestWorkspace:
    tournament_payload = payload.get("tournament")
    return GuestWorkspace(
        workspace_id=workspace_id,
        tournament=(
            TournamentConfig.model_validate(tournament_payload) if tournament_payload else None
        ),
        csrf_token=str(payload["csrf_token"]),
        weather=dict(payload.get("weather", {})),
        schedule_runs=dict(payload.get("schedule_runs", {})),
        drafts={
            draft_id: GeneratedProfileOption.model_validate(option)
            for draft_id, option in dict(payload.get("drafts", {})).items()
        },
        draft_revisions={
            str(key): int(value)
            for key, value in dict(payload.get("draft_revisions", {})).items()
        },
        rejected_drafts=set(payload.get("rejected_drafts", ())),
        idempotency=dict(payload.get("idempotency", {})),
        official_versions=list(payload.get("official_versions", ())),
        edits=dict(payload.get("edits", {})),
        disruptions=dict(payload.get("disruptions", {})),
        schedule_diffs=dict(payload.get("schedule_diffs", {})),
        feedback=list(payload.get("feedback", ())),
        constraint_confirmation=payload.get("constraint_confirmation"),
        audit_events=list(payload.get("audit_events", ())),
    )


class PostgresGuestWorkspaceStore(GuestWorkspaceStore):
    """Durable guest state with the same narrow API as the local memory store."""

    def __init__(self, engine: Engine, *, retention_days: int = 7) -> None:
        super().__init__()
        self._engine = engine
        self._retention = timedelta(days=retention_days)

    def create(self, tournament: TournamentConfig | None) -> tuple[str, GuestWorkspace]:
        token = secrets.token_urlsafe(32)
        digest = self._digest(token)
        now = datetime.now(UTC)
        workspace = GuestWorkspace(workspace_id=str(uuid4()), tournament=tournament)
        with Session(self._engine) as session, session.begin():
            session.add(
                PersistedWorkspace(
                    id=workspace.workspace_id,
                    identity_hash=digest,
                    mode="live",
                    created_at=now,
                    last_active_at=now,
                    expires_at=now + self._retention,
                )
            )
            session.add(
                WorkspaceSnapshot(
                    workspace_id=workspace.workspace_id,
                    payload=_workspace_payload(workspace),
                    updated_at=now,
                )
            )
        self._items[digest] = workspace
        return token, workspace

    def get(self, token: str | None) -> GuestWorkspace | None:
        if not token:
            return None
        digest = self._digest(token)
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            record = session.scalar(
                select(PersistedWorkspace).where(
                    PersistedWorkspace.identity_hash == digest,
                    PersistedWorkspace.deleted_at.is_(None),
                    PersistedWorkspace.expires_at > now,
                )
            )
            if record is None:
                self._items.pop(digest, None)
                return None
            snapshot = session.get(WorkspaceSnapshot, record.id)
            if snapshot is None:
                return None
            record.last_active_at = now
            record.expires_at = now + self._retention
            workspace = _workspace_from_payload(record.id, snapshot.payload)
        self._items[digest] = workspace
        return workspace

    def persist(self, token: str | None) -> None:
        if not token:
            return
        digest = self._digest(token)
        workspace = self._items.get(digest)
        if workspace is None:
            return
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            record = session.scalar(
                select(PersistedWorkspace).where(PersistedWorkspace.identity_hash == digest)
            )
            if record is None or record.deleted_at is not None:
                return
            snapshot = session.get(WorkspaceSnapshot, record.id)
            if snapshot is None:
                snapshot = WorkspaceSnapshot(workspace_id=record.id, payload={}, updated_at=now)
                session.add(snapshot)
            snapshot.payload = _workspace_payload(workspace)
            snapshot.updated_at = now
            record.last_active_at = now
            record.expires_at = now + self._retention

    def delete(self, token: str) -> None:
        digest = self._digest(token)
        with Session(self._engine) as session, session.begin():
            record = session.scalar(
                select(PersistedWorkspace).where(PersistedWorkspace.identity_hash == digest)
            )
            if record is not None:
                session.delete(record)
        self._items.pop(digest, None)
