from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import Field

from app.domain.common import UUID7, DomainModel, UtcDateTime


class ConstraintClassification(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class ConstraintStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ConstraintSource(StrEnum):
    ORGANIZER = "organizer"
    CHAT = "chat"
    SYSTEM = "system"
    DISRUPTION = "disruption"


class ConfirmationState(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class Constraint(DomainModel):
    id: UUID7
    type: str = Field(min_length=1, max_length=80)
    parameters: Mapping[str, object]
    classification: ConstraintClassification
    source: ConstraintSource
    status: ConstraintStatus
    explanation: str = Field(min_length=1, max_length=500)


class ConstraintSet(DomainModel):
    hard: tuple[Constraint, ...]
    soft: tuple[Constraint, ...]
    revision: int = Field(ge=0)
    confirmation_state: ConfirmationState
    confirmed_at: UtcDateTime | None = None
