from __future__ import annotations

from agents.extensions.memory import SQLAlchemySession

from app.domain.common import UUID7


def _async_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
        return database_url
    raise ValueError("agent sessions require PostgreSQL or async SQLite")


def create_agent_session(
    *,
    workspace_id: UUID7,
    database_url: str,
    create_tables: bool = False,
) -> SQLAlchemySession:
    return SQLAlchemySession.from_url(
        session_id=f"workspace:{workspace_id}",
        url=_async_database_url(database_url),
        create_tables=create_tables,
    )
