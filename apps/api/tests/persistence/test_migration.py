from __future__ import annotations

import importlib.util
from pathlib import Path

from app.persistence.models import Base
from sqlalchemy import create_engine, inspect


def _load_initial_revision():
    path = Path(__file__).parents[2] / "migrations" / "versions" / "0001_initial.py"
    spec = importlib.util.spec_from_file_location("initial_revision", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_initial_revision_has_upgrade_downgrade_metadata_and_round_trips() -> None:
    revision = _load_initial_revision()
    assert revision.revision == "0001_initial"
    assert revision.down_revision is None

    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        revision.upgrade(connection)
        assert set(inspect(connection).get_table_names()) == set(Base.metadata.tables)
        revision.downgrade(connection)
        assert inspect(connection).get_table_names() == []
        revision.upgrade(connection)
        assert set(inspect(connection).get_table_names()) == set(Base.metadata.tables)
