from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.tournament import MatchFormatPreset, TournamentConfig
from app.domain.venues import VenueSlot
from app.scheduling.intervals import allocation_bounds_utc_minutes
from app.scheduling.model import solve_hard_feasible_schedule
from app.scheduling.pairings import generate_match_graph
from app.scheduling.solver_result import SolverStatus
from tests.domain.factories import uuid7, valid_tournament


def _tournament_with_starts(
    preset: MatchFormatPreset,
    start_offsets_hours: tuple[int, ...],
    *,
    availability_hours: int = 4,
) -> TournamentConfig:
    tournament = valid_tournament()
    venue = tournament.venues[0]
    origin = datetime(2026, 9, 1, 4, tzinfo=UTC)
    slots = tuple(
        VenueSlot(
            id=uuid7(300 + index),
            venue_id=venue.id,
            starts_at_utc=origin + timedelta(hours=offset),
            ends_at_utc=origin + timedelta(hours=offset + availability_hours),
            local_date=(origin + timedelta(hours=offset))
            .astimezone(ZoneInfo(venue.iana_time_zone))
            .date(),
            availability="available",
            source="organizer",
        )
        for index, offset in enumerate(start_offsets_hours)
    )
    return TournamentConfig.model_validate(
        {
            **tournament.model_dump(),
            "match_format_preset": preset,
            "allocation_minutes": preset.allocation_minutes,
            "slots": slots,
        }
    )


def _solve_uniquely(tournament: TournamentConfig):
    matches = generate_match_graph(tournament)
    eligible = {
        match.id: frozenset((tournament.slots[index].id,))
        for index, match in enumerate(matches)
    }
    return solve_hard_feasible_schedule(tournament, matches, eligible)


def test_allocation_bounds_use_tournament_preset_duration() -> None:
    slot = valid_tournament().slots[0]

    t10_start, t10_end = allocation_bounds_utc_minutes(slot, 120)
    t20_start, t20_end = allocation_bounds_utc_minutes(slot, 240)

    assert t10_start == t20_start
    assert t10_end - t10_start == 120
    assert t20_end - t20_start == 240


def test_partial_same_venue_overlap_is_infeasible() -> None:
    tournament = _tournament_with_starts(
        MatchFormatPreset.T20,
        (0, 3, *range(8, 60, 4)),
    )

    assert _solve_uniquely(tournament).status is SolverStatus.INFEASIBLE


def test_identical_intervals_with_different_slot_ids_are_infeasible() -> None:
    tournament = _tournament_with_starts(
        MatchFormatPreset.T20,
        (0, 0, *range(4, 56, 4)),
    )

    assert _solve_uniquely(tournament).status is SolverStatus.INFEASIBLE


def test_allocation_block_must_fit_inside_slot_availability() -> None:
    tournament = _tournament_with_starts(
        MatchFormatPreset.T20,
        tuple(range(0, 60, 4)),
        availability_hours=3,
    )

    assert _solve_uniquely(tournament).status is SolverStatus.INFEASIBLE


def test_same_start_pattern_has_t10_capacity_but_not_t20_capacity() -> None:
    starts = tuple(range(0, 30, 2))
    t10 = _tournament_with_starts(MatchFormatPreset.T10, starts)
    t20 = _tournament_with_starts(MatchFormatPreset.T20, starts)

    assert _solve_uniquely(t10).status is SolverStatus.FEASIBLE
    assert _solve_uniquely(t20).status is SolverStatus.INFEASIBLE


def test_separated_t20_intervals_are_feasible() -> None:
    tournament = _tournament_with_starts(
        MatchFormatPreset.T20,
        tuple(range(0, 60, 4)),
    )

    assert _solve_uniquely(tournament).status is SolverStatus.FEASIBLE
