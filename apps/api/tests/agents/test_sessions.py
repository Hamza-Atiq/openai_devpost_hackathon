from __future__ import annotations

import asyncio
from pathlib import Path

from app.agents.sessions import create_agent_session
from tests.domain.factories import uuid7


def test_sqlalchemy_session_persists_workspace_scoped_items() -> None:
    database_path = Path(".test-agent-session.db").resolve()
    database_path.unlink(missing_ok=True)
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    session = create_agent_session(
        workspace_id=uuid7(800),
        database_url=database_url,
        create_tables=True,
    )

    async def exercise() -> None:
        try:
            await session.add_items([{"role": "user", "content": "Remember rain-first."}])
            assert await session.get_items() == [
                {"role": "user", "content": "Remember rain-first."}
            ]
        finally:
            await session._engine.dispose()

    asyncio.run(exercise())
    database_path.unlink(missing_ok=True)
    assert session.session_id == f"workspace:{uuid7(800)}"


def test_railway_postgres_url_is_converted_to_async_driver() -> None:
    session = create_agent_session(
        workspace_id=uuid7(801),
        database_url="postgresql://user:secret@example.test/crickops",
    )

    assert session._engine.url.drivername == "postgresql+asyncpg"
    assert "secret" not in repr(session._engine.url)
