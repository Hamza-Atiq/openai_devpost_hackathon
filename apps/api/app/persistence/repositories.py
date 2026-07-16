from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Base, WorkspaceOwned

WorkspaceModel = TypeVar("WorkspaceModel", bound=Base)


class WorkspaceRepository:
    """A mandatory workspace boundary for all guest-owned persistence access."""

    def __init__(self, session: Session, workspace_id: str) -> None:
        if not workspace_id:
            raise ValueError("workspace_id is required")
        self.session = session
        self.workspace_id = workspace_id

    def add(self, instance: WorkspaceModel) -> WorkspaceModel:
        if not isinstance(instance, WorkspaceOwned):
            raise TypeError("workspace repository only accepts workspace-owned models")
        if instance.workspace_id != self.workspace_id:
            raise ValueError("model is outside repository workspace scope")
        self.session.add(instance)
        return instance

    def get(self, model: type[WorkspaceModel], record_id: str) -> WorkspaceModel | None:
        self._require_scoped_model(model)
        return self.session.scalar(
            select(model).where(model.id == record_id, model.workspace_id == self.workspace_id)
        )

    def list(self, model: type[WorkspaceModel]) -> Sequence[WorkspaceModel]:
        self._require_scoped_model(model)
        return self.session.scalars(
            select(model).where(model.workspace_id == self.workspace_id).order_by(model.id)
        ).all()

    @staticmethod
    def _require_scoped_model(model: type[WorkspaceModel]) -> None:
        if not issubclass(model, WorkspaceOwned):
            raise TypeError("workspace repository requires a workspace-owned model")
