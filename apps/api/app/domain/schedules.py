from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import Field, model_validator

from app.domain.common import UUID7, DomainModel, UtcDateTime


class ScheduleProfile(StrEnum):
    BALANCED = "balanced"
    WEATHER_FIRST = "weather-first"
    FAIRNESS_FIRST = "fairness-first"
    CUSTOM = "custom"


class DraftStatus(StrEnum):
    QUEUED = "queued"
    SOLVING = "solving"
    VALIDATING = "validating"
    READY = "ready"
    INVALID = "invalid"
    INFEASIBLE = "infeasible"
    FAILED = "failed"
    CANCELLED = "cancelled"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class FixturePlacement(DomainModel):
    match_id: UUID7
    slot_id: UUID7
    venue_id: UUID7
    starts_at_utc: UtcDateTime
    ends_at_utc: UtcDateTime

    @model_validator(mode="after")
    def validate_interval(self) -> FixturePlacement:
        if self.ends_at_utc <= self.starts_at_utc:
            raise ValueError("ends_at_utc must be after starts_at_utc")
        return self


class ScheduleMetrics(DomainModel):
    weather_risk: float | None = Field(default=None, ge=0, le=100)
    weather_coverage: float = Field(default=0, ge=0, le=100)
    missing_coverage_penalty: float = Field(default=0, ge=0)
    group_rest_fairness: float = Field(default=0, ge=0, le=100)
    potential_knockout_rest: float = Field(default=0, ge=0, le=100)
    venue_balance: float = Field(default=0, ge=0, le=100)
    slot_balance: float = Field(default=0, ge=0, le=100)
    preference_satisfaction: float = Field(default=0, ge=0, le=100)
    change_cost: float = Field(default=0, ge=0)
    soft_violations: tuple[str, ...] = ()


class ValidationReport(DomainModel):
    valid: bool
    violations: tuple[str, ...] = ()


class ScheduleDraft(DomainModel):
    id: UUID7
    tournament_revision: int = Field(ge=0)
    constraint_revision: int = Field(ge=0)
    profile: ScheduleProfile
    status: DraftStatus
    placements: tuple[FixturePlacement, ...]
    metrics: ScheduleMetrics
    validation_report: ValidationReport
    created_at: UtcDateTime

    @model_validator(mode="after")
    def validate_placements(self) -> ScheduleDraft:
        if len(self.placements) != 15:
            raise ValueError("a Version 1 schedule must contain 15 placements")
        match_ids = tuple(placement.match_id for placement in self.placements)
        if len(set(match_ids)) != len(match_ids):
            raise ValueError("placements must reference a unique match")
        return self


class ScheduleVersion(DomainModel):
    id: UUID7
    version_number: int = Field(ge=1)
    approved_draft_id: UUID7
    approved_at: UtcDateTime
    supersedes_id: UUID7 | None = None


class ScheduleDiff(DomainModel):
    baseline_version_id: UUID7
    draft_id: UUID7
    unchanged: tuple[UUID7, ...] = ()
    moved: tuple[UUID7, ...] = ()
    added: tuple[UUID7, ...] = ()
    removed: tuple[UUID7, ...] = ()
    metric_deltas: Mapping[str, float] = {}
