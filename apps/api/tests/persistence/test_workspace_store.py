from __future__ import annotations

from app.api.workspace import PostgresGuestWorkspaceStore
from app.deployment.runtime import run_migrations
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


def test_postgres_store_restores_mutated_workspace_across_process_instances() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    run_migrations(engine)
    first_store = PostgresGuestWorkspaceStore(engine)
    token, workspace = first_store.create(None)
    workspace.weather = {"mode": "deterministic", "quality": "demo", "scenario_id": "rain"}
    workspace.official_versions.append({"version_id": "v1", "version_number": 1})
    first_store.persist(token)

    restored = PostgresGuestWorkspaceStore(engine).get(token)

    assert restored is not None
    assert restored.workspace_id == workspace.workspace_id
    assert restored.weather["scenario_id"] == "rain"
    assert restored.official_versions == [{"version_id": "v1", "version_number": 1}]


def test_postgres_store_delete_invalidates_the_guest_token() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    run_migrations(engine)
    store = PostgresGuestWorkspaceStore(engine)
    token, _workspace = store.create(None)

    store.delete(token)

    assert PostgresGuestWorkspaceStore(engine).get(token) is None
