from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.persistence.models import Base, GuestWorkspace, Tournament, TournamentRevision
from app.persistence.repositories import WorkspaceRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _workspace(workspace_id: str, identity_hash: str) -> GuestWorkspace:
    now = datetime.now(UTC)
    return GuestWorkspace(
        id=workspace_id,
        identity_hash=identity_hash,
        mode="live",
        created_at=now,
        last_active_at=now,
        expires_at=now + timedelta(days=7),
    )


def test_repository_never_reads_or_writes_another_workspace() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([_workspace("ws-a", "hash-a"), _workspace("ws-b", "hash-b")])
        session.add_all(
            [
                Tournament(id="t-a", workspace_id="ws-a", name="A", active=True),
                Tournament(id="t-b", workspace_id="ws-b", name="B", active=True),
            ]
        )
        session.commit()

        repository = WorkspaceRepository(session, "ws-a")
        assert repository.get(Tournament, "t-a").id == "t-a"
        assert repository.get(Tournament, "t-b") is None
        assert [row.id for row in repository.list(Tournament)] == ["t-a"]

        with pytest.raises(ValueError, match="workspace scope"):
            repository.add(Tournament(id="leak", workspace_id="ws-b", name="Leak"))


def test_immutable_revision_rejects_update_and_delete() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(_workspace("ws-a", "hash-a"))
        session.add(Tournament(id="t-a", workspace_id="ws-a", name="A", active=True))
        revision = TournamentRevision(
            id="rev-a",
            workspace_id="ws-a",
            tournament_id="t-a",
            revision=1,
            snapshot={"name": "A"},
            input_digest="digest",
            created_at=now,
        )
        session.add(revision)
        session.commit()

        revision.input_digest = "changed"
        with pytest.raises(ValueError, match="immutable"):
            session.commit()
        session.rollback()

        revision = session.get(TournamentRevision, "rev-a")
        session.delete(revision)
        with pytest.raises(ValueError, match="immutable"):
            session.commit()
