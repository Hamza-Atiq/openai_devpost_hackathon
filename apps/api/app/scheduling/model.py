from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from ortools.sat.python import cp_model

from app.domain.matches import MatchDefinition
from app.domain.tournament import TournamentConfig
from app.domain.venues import SlotAvailability
from app.scheduling.intervals import add_venue_interval_constraints
from app.scheduling.pairings import generate_match_graph
from app.scheduling.solver_result import (
    FeasibleSolverResult,
    InfeasibilityCode,
    InfeasibleSolverResult,
    SolverPlacement,
    SolverResult,
)


def solve_hard_feasible_schedule(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
    eligible_slot_ids_by_match: Mapping[UUID, frozenset[UUID]],
    *,
    required_slot_by_match: Mapping[UUID, UUID] | None = None,
) -> SolverResult:
    """Solve the TASK-011 placement shell with deterministic CP-SAT settings."""
    ordered_matches = tuple(sorted(matches, key=lambda match: match.sequence))
    if ordered_matches != generate_match_graph(tournament):
        return InfeasibleSolverResult(
            evidence_codes=(InfeasibilityCode.INVALID_MATCH_GRAPH,),
            cp_sat_status="PRECHECK_REJECTED",
        )

    ordered_slots = tuple(
        sorted(tournament.slots, key=lambda slot: (slot.starts_at_utc, str(slot.id)))
    )
    match_ids = {match.id for match in ordered_matches}
    slot_ids = {slot.id for slot in ordered_slots}
    pins = required_slot_by_match or {}
    has_invalid_pin = any(
        match_id not in match_ids or slot_id not in slot_ids
        for match_id, slot_id in pins.items()
    )
    if has_invalid_pin:
        return InfeasibleSolverResult(
            evidence_codes=(InfeasibilityCode.INVALID_PIN,),
            cp_sat_status="PRECHECK_REJECTED",
        )

    model = cp_model.CpModel()
    placement = {
        (match.id, slot.id): model.new_bool_var(f"place_{match.sequence}_{slot.id}")
        for match in ordered_matches
        for slot in ordered_slots
    }

    for match in ordered_matches:
        model.add_exactly_one(placement[(match.id, slot.id)] for slot in ordered_slots)
        eligible_ids = eligible_slot_ids_by_match.get(match.id, frozenset())
        for slot in ordered_slots:
            if slot.availability is not SlotAvailability.AVAILABLE or slot.id not in eligible_ids:
                model.add(placement[(match.id, slot.id)] == 0)

    for slot in ordered_slots:
        model.add_at_most_one(placement[(match.id, slot.id)] for match in ordered_matches)

    add_venue_interval_constraints(
        model,
        placement,
        ordered_matches,
        ordered_slots,
        tournament.allocation_minutes,
    )

    for match_id, slot_id in pins.items():
        model.add(placement[(match_id, slot_id)] == 1)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 30
    cp_status = solver.solve(model)
    cp_status_name = solver.status_name(cp_status)

    if cp_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        placements = tuple(
            SolverPlacement(match_id=match.id, slot_id=slot.id)
            for match in ordered_matches
            for slot in ordered_slots
            if solver.boolean_value(placement[(match.id, slot.id)])
        )
        return FeasibleSolverResult(placements=placements, cp_sat_status=cp_status_name)

    evidence_code = {
        cp_model.INFEASIBLE: InfeasibilityCode.CP_SAT_INFEASIBLE,
        cp_model.MODEL_INVALID: InfeasibilityCode.CP_SAT_MODEL_INVALID,
        cp_model.UNKNOWN: InfeasibilityCode.CP_SAT_UNKNOWN,
    }.get(cp_status, InfeasibilityCode.CP_SAT_UNKNOWN)
    return InfeasibleSolverResult(
        evidence_codes=(evidence_code,),
        cp_sat_status=cp_status_name,
    )
