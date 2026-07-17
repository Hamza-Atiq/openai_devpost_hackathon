from __future__ import annotations

import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.deployment.runtime import (
    check_database,
    normalize_database_url,
    run_migrations,
    run_retention_cleanup,
)
from app.persistence.models import Base, GuestWorkspace
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[4]


def test_normalize_database_url_selects_the_sync_psycopg_driver() -> None:
    assert (
        normalize_database_url("postgresql://user:pass@db.example/crickops")
        == "postgresql+psycopg://user:pass@db.example/crickops"
    )
    assert normalize_database_url("sqlite+pysqlite:///:memory:") == "sqlite+pysqlite:///:memory:"


def test_migrations_create_the_current_schema_idempotently() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    run_migrations(engine)
    run_migrations(engine)

    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables)
    check_database(engine)


def test_retention_worker_marks_expired_then_hard_deletes_after_grace() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    run_migrations(engine)
    now = datetime(2026, 7, 17, 8, 0, tzinfo=UTC)
    with Session(engine) as session:
        session.add_all(
            [
                GuestWorkspace(
                    id="expired",
                    identity_hash="expired-hash",
                    mode="live",
                    created_at=now - timedelta(days=8),
                    last_active_at=now - timedelta(days=8),
                    expires_at=now - timedelta(days=1),
                ),
                GuestWorkspace(
                    id="active",
                    identity_hash="active-hash",
                    mode="live",
                    created_at=now,
                    last_active_at=now,
                    expires_at=now + timedelta(days=7),
                ),
            ]
        )
        session.commit()

    first = run_retention_cleanup(engine, now=now)
    assert first.marked_deleted == 1
    assert first.hard_deleted == 0

    second = run_retention_cleanup(engine, now=now + timedelta(hours=25))
    assert second.marked_deleted == 0
    assert second.hard_deleted == 1
    with Session(engine) as session:
        assert session.scalars(select(GuestWorkspace.id)).all() == ["active"]


def test_railway_uses_the_container_migration_and_process_entrypoint() -> None:
    railway = tomllib.loads((ROOT / "railway.toml").read_text(encoding="utf-8"))
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert railway["build"] == {"builder": "DOCKERFILE", "dockerfilePath": "Dockerfile"}
    assert railway["deploy"]["preDeployCommand"] == [
        "uv run --directory apps/api python -m app.deployment.runtime migrate"
    ]
    assert railway["deploy"]["startCommand"].endswith("app.deployment.runtime serve")
    assert "USER crickops" in dockerfile
    assert ".env*" in dockerignore
