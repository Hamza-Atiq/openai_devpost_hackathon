from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from app.domain.common import UUID7, DomainModel


class MatchStage(StrEnum):
    GROUP = "group"
    SEMIFINAL = "semifinal"
    FINAL = "final"


class MatchDefinition(DomainModel):
    id: UUID7
    stage: MatchStage
    sequence: int = Field(ge=1, le=15)
    participant_a: str = Field(min_length=1, max_length=100)
    participant_b: str = Field(min_length=1, max_length=100)
    dependency_ids: tuple[UUID7, ...] = ()

    @model_validator(mode="after")
    def validate_dependencies(self) -> MatchDefinition:
        if self.id in self.dependency_ids:
            raise ValueError("a match cannot depend on itself")
        if len(set(self.dependency_ids)) != len(self.dependency_ids):
            raise ValueError("dependency_ids must be unique")
        return self
