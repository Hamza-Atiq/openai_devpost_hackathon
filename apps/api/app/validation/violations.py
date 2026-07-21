from __future__ import annotations

from enum import StrEnum

from app.domain.common import UUID7, DomainModel, UtcDateTime


class ViolationCode(StrEnum):
    INVALID_MATCH_GRAPH = "invalid_match_graph"
    MISSING_MATCH = "missing_match"
    DUPLICATE_MATCH = "duplicate_match"
    FABRICATED_MATCH = "fabricated_match"
    UNKNOWN_SLOT = "unknown_slot"
    UNAVAILABLE_SLOT = "unavailable_slot"
    PLACEMENT_MISMATCH = "placement_mismatch"
    ALLOCATION_OVERFLOW = "allocation_overflow"
    VENUE_OVERLAP = "venue_overlap"
    TOURNAMENT_CONCURRENCY = "tournament_concurrency"
    TEAM_OVERLAP = "team_overlap"
    TEAM_LOCAL_DAY = "team_local_day"
    REST_VIOLATION = "rest_violation"
    STAGE_CHRONOLOGY = "stage_chronology"
    QUALIFICATION_PATH = "qualification_path"


class ValidationViolation(DomainModel):
    code: ViolationCode
    message: str
    match_ids: tuple[UUID7, ...] = ()


class ValidationCheck(DomainModel):
    name: str
    passed: bool


class IndependentValidationReport(DomainModel):
    valid: bool
    input_digest: str
    placement_digest: str
    validator_version: str
    checks: tuple[ValidationCheck, ...]
    violations: tuple[ValidationViolation, ...]
    generated_at: UtcDateTime

    @property
    def violation_codes(self) -> tuple[ViolationCode, ...]:
        return tuple(violation.code for violation in self.violations)
