from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import Field

from app.domain.common import UUID7, DomainModel, UtcDateTime


class ActorType(StrEnum):
    ORGANIZER = "organizer"
    AGENT = "agent"
    SYSTEM = "system"


class AgentProvenance(DomainModel):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    decision_id: UUID7


class AuditEvent(DomainModel):
    id: UUID7
    workspace_id: UUID7
    tournament_id: UUID7
    actor_type: ActorType
    event_type: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    structured_payload: Mapping[str, object]
    occurred_at: UtcDateTime
    agent_provenance: AgentProvenance | None = None
