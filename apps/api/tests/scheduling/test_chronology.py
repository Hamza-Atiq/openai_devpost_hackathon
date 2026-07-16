from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.matches import MatchDefinition
from app.domain.tournament import TournamentConfig
from app.domain.venues import Venue, VenueSlot
from app.scheduling.model import solve_hard_feasible_schedule
from app.scheduling.pairings import generate_match_graph
from app.scheduling.solver_result import SolverStatus
from tests.domain.factories import valid_tournament


def _baseline_slot_ids(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
) -> dict[object, object]:
    group_a = matches[:6]
    group_b = matches[6:12]
    assignment = {
        match.id: tournament.slots[index * 2].id for index, match in enumerate(group_a)
    }
    assignment.update(
        {match.id: tournament.slots[index * 2 + 1].id for index, match in enumerate(group_b)}
    )
    assignment.update(
        {
            matches[12].id: tournament.slots[12].id,
            matches[13].id: tournament.slots[13].id,
            matches[14].id: tournament.slots[14].id,
        }
    )
    return assignment


def _solve_assignment(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
    assignment: dict[object, object],
    *,
    minimum_rest_minutes: int = 0,
):
    eligible = {match_id: frozenset((slot_id,)) for match_id, slot_id in assignment.items()}
    return solve_hard_feasible_schedule(
        tournament,
        matches,
        eligible,
        minimum_rest_minutes=minimum_rest_minutes,
    )


def test_valid_stage_order_allows_both_semifinals_on_same_local_day() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)

    result = _solve_assignment(tournament, matches, _baseline_slot_ids(tournament, matches))

    assert result.status is SolverStatus.FEASIBLE


def test_team_cannot_play_twice_on_same_local_day_when_intervals_do_not_overlap() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    assignment = _baseline_slot_ids(tournament, matches)
    assignment[matches[1].id], assignment[matches[6].id] = (
        assignment[matches[6].id],
        assignment[matches[1].id],
    )

    assert _solve_assignment(tournament, matches, assignment).status is SolverStatus.INFEASIBLE


def test_all_group_matches_must_finish_before_either_semifinal() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    assignment = _baseline_slot_ids(tournament, matches)
    assignment[matches[5].id], assignment[matches[12].id] = (
        assignment[matches[12].id],
        assignment[matches[5].id],
    )

    assert _solve_assignment(tournament, matches, assignment).status is SolverStatus.INFEASIBLE


def test_both_semifinals_must_finish_before_final() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    assignment = _baseline_slot_ids(tournament, matches)
    assignment[matches[12].id], assignment[matches[14].id] = (
        assignment[matches[14].id],
        assignment[matches[12].id],
    )

    assert _solve_assignment(tournament, matches, assignment).status is SolverStatus.INFEASIBLE


def test_minimum_rest_protects_every_possible_group_to_semifinal_path() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)

    result = _solve_assignment(
        tournament,
        matches,
        _baseline_slot_ids(tournament, matches),
        minimum_rest_minutes=24 * 60,
    )

    assert result.status is SolverStatus.INFEASIBLE


def test_dst_fallback_uses_venue_local_calendar_day() -> None:
    tournament = valid_tournament()
    time_zone = "America/New_York"
    venues = tuple(
        Venue.model_validate({**venue.model_dump(), "iana_time_zone": time_zone})
        for venue in tournament.venues
    )
    origin = datetime(2026, 11, 1, 4, tzinfo=UTC)
    slots = tuple(
        VenueSlot.model_validate(
            {
                **slot.model_dump(),
                "starts_at_utc": origin
                + timedelta(days=index // 2, hours=(index % 2) * 5),
                "ends_at_utc": origin
                + timedelta(days=index // 2, hours=(index % 2) * 5 + 4),
                "local_date": (
                    origin + timedelta(days=index // 2, hours=(index % 2) * 5)
                )
                .astimezone(ZoneInfo(time_zone))
                .date(),
            }
        )
        for index, slot in enumerate(tournament.slots)
    )
    tournament = TournamentConfig.model_validate(
        {
            **tournament.model_dump(),
            "start_date": slots[0].local_date,
            "end_date": slots[0].local_date + timedelta(days=9),
            "venues": venues,
            "slots": slots,
        }
    )
    matches = generate_match_graph(tournament)
    assignment = _baseline_slot_ids(tournament, matches)
    assignment[matches[1].id], assignment[matches[6].id] = (
        assignment[matches[6].id],
        assignment[matches[1].id],
    )

    assert slots[0].local_date == slots[1].local_date
    assert _solve_assignment(tournament, matches, assignment).status is SolverStatus.INFEASIBLE
