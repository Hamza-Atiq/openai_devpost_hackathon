from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.domain.common import DomainModel, UtcDateTime


class AgentMode(StrEnum):
    GPT_5_6 = "gpt-5.6"
    FALLBACK_MODEL = "fallback-model"
    DETERMINISTIC = "deterministic"


class AgentRole(StrEnum):
    TOURNAMENT_DIRECTOR = "tournament_director"
    RULES_CONSTRAINT = "rules_constraint"
    SCHEDULING_STRATEGY = "scheduling_strategy"
    WEATHER_INTELLIGENCE = "weather_intelligence"
    FAIRNESS_LOGISTICS = "fairness_logistics"
    DISRUPTION_RECOVERY = "disruption_recovery"


class ValidationStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"


class ToolOutcomeStatus(StrEnum):
    VALIDATED = "validated"
    REJECTED = "rejected"
    ERROR = "error"


class ToolOutcome(DomainModel):
    tool_name: str = Field(min_length=1, max_length=120)
    status: ToolOutcomeStatus
    deterministic_authority: bool
    validation_status: ValidationStatus
    output_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    detail: str | None = Field(default=None, max_length=240)


class EvidenceRef(DomainModel):
    evidence_id: str = Field(min_length=1, max_length=240)
    evidence_kind: str = Field(min_length=1, max_length=120)
    revision: int = Field(ge=0)
    consumed_fields: tuple[str, ...] = Field(min_length=1)


class AgentDecision(DomainModel):
    role: AgentRole
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    occurred_at: UtcDateTime
    summary: str = Field(min_length=1, max_length=1200)
    validation_status: ValidationStatus
    requires_organizer_approval: bool
    clarification_questions: tuple[str, ...] = ()
    tool_outcomes: tuple[ToolOutcome, ...] = ()


class DeterministicModeResult(DomainModel):
    mode: Literal[AgentMode.DETERMINISTIC] = AgentMode.DETERMINISTIC
    agent_response: None = None
    fabricated_response: Literal[False] = False
    reason: str = Field(min_length=1, max_length=500)
    available_capabilities: tuple[str, ...] = (
        "structured tournament setup",
        "schedule generation and validation",
        "three optimization profiles",
        "deterministic demo weather",
        "schedule repair",
        "approved schedules and audit history",
    )
