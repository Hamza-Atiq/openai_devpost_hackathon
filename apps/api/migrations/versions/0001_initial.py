"""Create the complete CrickOps Version 1 relational schema."""

from __future__ import annotations

from typing import Any

from app.persistence.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _connection(bind: Any | None) -> Any:
    if bind is not None:
        return bind
    try:
        from alembic import op
    except ImportError as exc:  # pragma: no cover - exercised in deployed migration environment
        raise RuntimeError("Alembic is required when no SQLAlchemy connection is supplied") from exc
    return op.get_bind()


def upgrade(bind: Any | None = None) -> None:
    Base.metadata.create_all(_connection(bind), checkfirst=False)


def downgrade(bind: Any | None = None) -> None:
    Base.metadata.drop_all(_connection(bind), checkfirst=False)
