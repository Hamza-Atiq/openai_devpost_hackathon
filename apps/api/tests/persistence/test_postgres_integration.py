from __future__ import annotations

import importlib.util
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app.persistence.models import Base, GuestWorkspace, Tournament
from app.persistence.repositories import WorkspaceRepository
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session


def _database_url() -> str | None:
    return os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")


def _psycopg_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def _load_initial_revision():
    path = Path(__file__).parents[2] / "migrations" / "versions" / "0001_initial.py"
    spec = importlib.util.spec_from_file_location("postgres_initial_revision", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(_database_url() is None, reason="PostgreSQL integration URL not configured")
def test_postgres_migration_and_workspace_isolation() -> None:
    schema = f"qg12_{uuid4().hex}"
    engine = create_engine(
        _psycopg_url(_database_url() or ""),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )
    revision = _load_initial_revision()
    quoted_schema = f'"{schema}"'
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(f"CREATE SCHEMA {quoted_schema}")
            connection.exec_driver_sql(f"SET search_path TO {quoted_schema}")
            revision.upgrade(connection)
            assert set(inspect(connection).get_table_names()) == set(Base.metadata.tables)

        now = datetime.now(UTC)
        with Session(engine) as session:
            session.execute(text(f"SET search_path TO {quoted_schema}"))
            session.add_all(
                [
                    GuestWorkspace(
                        id="ws-a",
                        identity_hash="a",
                        mode="live",
                        created_at=now,
                        last_active_at=now,
                        expires_at=now + timedelta(days=7),
                    ),
                    GuestWorkspace(
                        id="ws-b",
                        identity_hash="b",
                        mode="live",
                        created_at=now,
                        last_active_at=now,
                        expires_at=now + timedelta(days=7),
                    ),
                    Tournament(id="t-a", workspace_id="ws-a", name="A", active=True),
                    Tournament(id="t-b", workspace_id="ws-b", name="B", active=True),
                ]
            )
            session.commit()
            repository = WorkspaceRepository(session, "ws-a")
            assert repository.get(Tournament, "t-a") is not None
            assert repository.get(Tournament, "t-b") is None

        with engine.begin() as connection:
            connection.exec_driver_sql(f"SET search_path TO {quoted_schema}")
            revision.downgrade(connection)
            assert inspect(connection).get_table_names() == []
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
        engine.dispose()
