from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.domain.common import UUID7, DomainModel
from app.domain.matches import MatchDefinition
from app.domain.schedules import FixturePlacement
from app.domain.tournament import TournamentConfig
from app.scheduling.model import solve_hard_feasible_schedule
from app.scheduling.repair_objectives import (
    bounded_quality_costs,
    changed_count_costs,
    movement_costs,
)
from app.scheduling.solver_result import FeasibleSolverResult
from app.validation.validator import validate_schedule
from app.validation.violations import IndependentValidationReport


class RepairStatus(StrEnum):
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"


class RepairPassOptima(DomainModel):
    changed_count: int
    movement_cost: int
    quality_cost: int


class RepairResult(DomainModel):
    status: RepairStatus
    placements: tuple[FixturePlacement, ...] = ()
    pass_optima: RepairPassOptima | None = None
    validation_report: IndependentValidationReport | None = None
    preserved_match_ids: tuple[UUID7, ...] = ()
    changed_match_ids: tuple[UUID7, ...] = ()


def _placements(
    tournament: TournamentConfig,
    result: FeasibleSolverResult,
) -> tuple[FixturePlacement, ...]:
    slot_by_id = {slot.id: slot for slot in tournament.slots}
    return tuple(
        FixturePlacement(
            match_id=item.match_id,
            slot_id=item.slot_id,
            venue_id=slot_by_id[item.slot_id].venue_id,
            starts_at_utc=slot_by_id[item.slot_id].starts_at_utc,
            ends_at_utc=slot_by_id[item.slot_id].starts_at_utc
            + timedelta(minutes=tournament.allocation_minutes),
        )
        for item in result.placements
    )


def repair_schedule(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
    baseline: Sequence[FixturePlacement],
    eligible_slot_ids_by_match: Mapping[UUID, frozenset[UUID]],
    *,
    generated_at: datetime,
    minimum_rest_minutes: int = 0,
    quality_cost_by_placement: Mapping[tuple[UUID, UUID], int] | None = None,
) -> RepairResult:
    change_cost = changed_count_costs(tournament, baseline)
    movement_cost = movement_costs(tournament, baseline)
    quality_cost = bounded_quality_costs(tournament, baseline, quality_cost_by_placement)

    pass_one = solve_hard_feasible_schedule(
        tournament,
        matches,
        eligible_slot_ids_by_match,
        minimum_rest_minutes=minimum_rest_minutes,
        objective_cost_by_placement=change_cost,
    )
    if not isinstance(pass_one, FeasibleSolverResult):
        return RepairResult(status=RepairStatus.INFEASIBLE)
    pass_two = solve_hard_feasible_schedule(
        tournament,
        matches,
        eligible_slot_ids_by_match,
        minimum_rest_minutes=minimum_rest_minutes,
        objective_cost_by_placement=movement_cost,
        fixed_cost_totals=((change_cost, pass_one.objective_value),),
    )
    if not isinstance(pass_two, FeasibleSolverResult):
        return RepairResult(status=RepairStatus.INFEASIBLE)
    pass_three = solve_hard_feasible_schedule(
        tournament,
        matches,
        eligible_slot_ids_by_match,
        minimum_rest_minutes=minimum_rest_minutes,
        objective_cost_by_placement=quality_cost,
        fixed_cost_totals=(
            (change_cost, pass_one.objective_value),
            (movement_cost, pass_two.objective_value),
        ),
    )
    if not isinstance(pass_three, FeasibleSolverResult):
        return RepairResult(status=RepairStatus.INFEASIBLE)

    placements = _placements(tournament, pass_three)
    validation_report = validate_schedule(
        tournament,
        matches,
        placements,
        generated_at=generated_at,
        minimum_rest_minutes=minimum_rest_minutes,
    )
    if not validation_report.valid:
        return RepairResult(status=RepairStatus.INFEASIBLE)
    baseline_slot = {placement.match_id: placement.slot_id for placement in baseline}
    changed = tuple(
        placement.match_id
        for placement in placements
        if placement.slot_id != baseline_slot[placement.match_id]
    )
    preserved = tuple(
        placement.match_id
        for placement in placements
        if placement.slot_id == baseline_slot[placement.match_id]
    )
    return RepairResult(
        status=RepairStatus.FEASIBLE,
        placements=placements,
        pass_optima=RepairPassOptima(
            changed_count=pass_one.objective_value,
            movement_cost=pass_two.objective_value,
            quality_cost=pass_three.objective_value,
        ),
        validation_report=validation_report,
        preserved_match_ids=preserved,
        changed_match_ids=changed,
    )
