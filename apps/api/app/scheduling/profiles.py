from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.domain.common import DomainModel
from app.domain.matches import MatchDefinition
from app.domain.schedules import FixturePlacement, ScheduleMetrics, ScheduleProfile
from app.domain.tournament import TournamentConfig
from app.optimization.config import (
    config_checksum,
    load_optimization_config,
    normalize_custom_priorities,
)
from app.scheduling.model import solve_hard_feasible_schedule
from app.scheduling.solver_result import FeasibleSolverResult
from app.validation.validator import validate_schedule
from app.validation.violations import IndependentValidationReport

MetricEvaluator = Callable[[ScheduleProfile, tuple[FixturePlacement, ...]], ScheduleMetrics]
PlacementKey = tuple[UUID, UUID]
ComponentPenalties = Mapping[str, Mapping[PlacementKey, int]]


def _weighted_objective_costs(
    component_penalties: ComponentPenalties,
    profile_weights: Mapping[str, Decimal | int],
) -> dict[PlacementKey, int]:
    keys = {
        key
        for penalties in component_penalties.values()
        for key in penalties
    }
    for penalties in component_penalties.values():
        if any(value < 0 or value > 100 for value in penalties.values()):
            raise ValueError("soft objective penalties must be between 0 and 100")
    return {
        key: int(
            sum(
                Decimal(str(profile_weights.get(component, 0))) * Decimal(penalties.get(key, 0))
                for component, penalties in component_penalties.items()
            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        for key in keys
    }


class GeneratedProfileOption(DomainModel):
    profile: ScheduleProfile
    weights: Mapping[str, Decimal]
    config_version: str
    config_checksum: str
    placements: tuple[FixturePlacement, ...]
    metrics: ScheduleMetrics
    validation_report: IndependentValidationReport


class ProfileGenerationFailure(DomainModel):
    profile: ScheduleProfile
    reason: str


class ProfileGenerationBatch(DomainModel):
    options: tuple[GeneratedProfileOption, ...]
    failures: tuple[ProfileGenerationFailure, ...]


def _fixture_placements(
    tournament: TournamentConfig,
    solver_result: FeasibleSolverResult,
) -> tuple[FixturePlacement, ...]:
    slot_by_id = {slot.id: slot for slot in tournament.slots}
    return tuple(
        FixturePlacement(
            match_id=placement.match_id,
            slot_id=placement.slot_id,
            venue_id=slot_by_id[placement.slot_id].venue_id,
            starts_at_utc=slot_by_id[placement.slot_id].starts_at_utc,
            ends_at_utc=slot_by_id[placement.slot_id].starts_at_utc
            + timedelta(minutes=tournament.allocation_minutes),
        )
        for placement in solver_result.placements
    )


def generate_profile_options(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
    eligible_slot_ids_by_match: Mapping[UUID, frozenset[UUID]],
    *,
    generated_at: datetime,
    metric_evaluator: MetricEvaluator,
    custom_priorities: dict[str, int] | None = None,
    minimum_rest_minutes: int = 0,
    component_penalties: ComponentPenalties | None = None,
) -> ProfileGenerationBatch:
    config = load_optimization_config()
    profile_order = [
        ScheduleProfile.BALANCED,
        ScheduleProfile.WEATHER_FIRST,
        ScheduleProfile.FAIRNESS_FIRST,
    ]
    weights: dict[ScheduleProfile, Mapping[str, Decimal | int]] = {
        profile: config.profiles[profile.value].weights.model_dump(exclude={"schema_version"})
        for profile in profile_order
    }
    if custom_priorities is not None:
        profile_order.append(ScheduleProfile.CUSTOM)
        weights[ScheduleProfile.CUSTOM] = normalize_custom_priorities(custom_priorities)

    checksum = config_checksum()

    def generate(profile: ScheduleProfile) -> GeneratedProfileOption | ProfileGenerationFailure:
        objective_costs = (
            _weighted_objective_costs(component_penalties, weights[profile])
            if component_penalties is not None
            else None
        )
        solver_result = solve_hard_feasible_schedule(
            tournament,
            matches,
            eligible_slot_ids_by_match,
            minimum_rest_minutes=minimum_rest_minutes,
            objective_cost_by_placement=objective_costs,
        )
        if not isinstance(solver_result, FeasibleSolverResult):
            return ProfileGenerationFailure(profile=profile, reason=solver_result.cp_sat_status)
        placements = _fixture_placements(tournament, solver_result)
        report = validate_schedule(
            tournament,
            matches,
            placements,
            generated_at=generated_at,
            minimum_rest_minutes=minimum_rest_minutes,
        )
        if not report.valid:
            return ProfileGenerationFailure(profile=profile, reason="independent_validation_failed")
        return GeneratedProfileOption(
            profile=profile,
            weights=weights[profile],
            config_version=config.version,
            config_checksum=checksum,
            placements=placements,
            metrics=metric_evaluator(profile, placements),
            validation_report=report,
        )

    with ThreadPoolExecutor(max_workers=len(profile_order)) as executor:
        generated = tuple(executor.map(generate, profile_order))
    return ProfileGenerationBatch(
        options=tuple(item for item in generated if isinstance(item, GeneratedProfileOption)),
        failures=tuple(item for item in generated if isinstance(item, ProfileGenerationFailure)),
    )
