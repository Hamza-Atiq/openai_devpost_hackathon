from __future__ import annotations

from enum import StrEnum
from typing import Literal

from app.domain.common import UUID7, DomainModel


class SolverStatus(StrEnum):
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"


class InfeasibilityCode(StrEnum):
    INVALID_MATCH_GRAPH = "invalid_match_graph"
    INVALID_PIN = "invalid_pin"
    CP_SAT_INFEASIBLE = "cp_sat_infeasible"
    CP_SAT_MODEL_INVALID = "cp_sat_model_invalid"
    CP_SAT_UNKNOWN = "cp_sat_unknown"


class SolverPlacement(DomainModel):
    match_id: UUID7
    slot_id: UUID7


class FeasibleSolverResult(DomainModel):
    status: Literal[SolverStatus.FEASIBLE] = SolverStatus.FEASIBLE
    placements: tuple[SolverPlacement, ...]
    evidence_codes: tuple[InfeasibilityCode, ...] = ()
    cp_sat_status: str


class InfeasibleSolverResult(DomainModel):
    status: Literal[SolverStatus.INFEASIBLE] = SolverStatus.INFEASIBLE
    placements: tuple[()] = ()
    evidence_codes: tuple[InfeasibilityCode, ...]
    cp_sat_status: str


type SolverResult = FeasibleSolverResult | InfeasibleSolverResult
