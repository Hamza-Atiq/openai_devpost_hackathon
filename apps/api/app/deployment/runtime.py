from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import uvicorn
from sqlalchemy import Engine, create_engine, delete, inspect, select, update
from sqlalchemy.orm import Session

from app.persistence.models import Base, GuestWorkspace


@dataclass(frozen=True, slots=True)
class RetentionResult:
    marked_deleted: int
    hard_deleted: int


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def database_engine(url: str | None = None) -> Engine:
    configured = url or os.environ.get("DATABASE_URL")
    if not configured:
        raise RuntimeError("DATABASE_URL is required")
    return create_engine(normalize_database_url(configured), pool_pre_ping=True)


def run_migrations(engine: Engine) -> None:
    """Apply the idempotent baseline schema before a deployment becomes active."""
    Base.metadata.create_all(engine)


def check_database(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(select(1))
        present = set(inspect(connection).get_table_names())
    missing = set(Base.metadata.tables) - present
    if missing:
        raise RuntimeError(f"database schema is incomplete: {len(missing)} tables missing")


def run_retention_cleanup(
    engine: Engine,
    *,
    now: datetime | None = None,
    hard_delete_grace: timedelta = timedelta(hours=24),
) -> RetentionResult:
    current = now or datetime.now(UTC)
    with Session(engine) as session, session.begin():
        marked = session.execute(
            update(GuestWorkspace)
            .where(GuestWorkspace.deleted_at.is_(None), GuestWorkspace.expires_at <= current)
            .values(deleted_at=current)
        ).rowcount
        hard_deleted = session.execute(
            delete(GuestWorkspace).where(
                GuestWorkspace.deleted_at.is_not(None),
                GuestWorkspace.deleted_at <= current - hard_delete_grace,
            )
        ).rowcount
    return RetentionResult(marked_deleted=marked or 0, hard_deleted=hard_deleted or 0)


def _serve() -> None:
    process_type = os.environ.get("CRICKOPS_PROCESS_TYPE", "api").strip().lower()
    target = "app.deployment.worker:app" if process_type == "worker" else "app.main:app"
    uvicorn.run(target, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))


def main() -> None:
    parser = argparse.ArgumentParser(description="CrickOps deployment controls")
    parser.add_argument("command", choices=("migrate", "check", "cleanup", "serve"))
    args = parser.parse_args()
    if args.command == "serve":
        _serve()
        return
    engine = database_engine()
    try:
        if args.command == "migrate":
            run_migrations(engine)
        elif args.command == "check":
            check_database(engine)
        else:
            result = run_retention_cleanup(engine)
            print(
                f"retention cleanup complete: marked={result.marked_deleted} "
                f"hard_deleted={result.hard_deleted}"
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
