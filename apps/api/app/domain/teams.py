from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.common import UUID7, DomainModel


class Team(DomainModel):
    id: UUID7
    display_name: str = Field(min_length=1, max_length=100)
    group_id: UUID7


class Group(DomainModel):
    id: UUID7
    code: Literal["A", "B"]
    team_ids: tuple[UUID7, UUID7, UUID7, UUID7]
