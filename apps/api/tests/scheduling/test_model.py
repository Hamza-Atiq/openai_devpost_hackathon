from __future__ import annotations

from app.domain.venues import SlotAvailability, VenueSlot
from app.scheduling.model import solve_hard_feasible_schedule
from app.scheduling.pairings import generate_match_graph
from app.scheduling.solver_result import InfeasibilityCode, SolverStatus
from tests.domain.factories import valid_tournament


def test_solves_exactly_one_unique_eligible_slot_per_fixed_match() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    eligible = {
        match.id: frozenset((tournament.slots[index].id,))
        for index, match in enumerate(matches)
    }

    result = solve_hard_feasible_schedule(tournament, matches, eligible)

    assert result.status is SolverStatus.FEASIBLE
    assert len(result.placements) == 15
    assert len({placement.match_id for placement in result.placements}) == 15
    assert len({placement.slot_id for placement in result.placements}) == 15
    assert all(placement.slot_id in eligible[placement.match_id] for placement in result.placements)


def test_returns_repeatable_placements_for_identical_inputs() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    available_ids = frozenset(slot.id for slot in tournament.slots)
    eligible = {match.id: available_ids for match in matches}

    first = solve_hard_feasible_schedule(tournament, matches, eligible)
    second = solve_hard_feasible_schedule(tournament, matches, eligible)

    assert first == second


def test_returns_typed_infeasible_result_when_capacity_is_insufficient() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    fourteen_slots = frozenset(slot.id for slot in tournament.slots[:14])
    eligible = {match.id: fourteen_slots for match in matches}

    result = solve_hard_feasible_schedule(tournament, matches, eligible)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.placements == ()
    assert InfeasibilityCode.CP_SAT_INFEASIBLE in result.evidence_codes


def test_unavailable_slot_cannot_satisfy_a_required_pin() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    blocked = tournament.slots[0]
    blocked_slot = VenueSlot.model_validate(
        {**blocked.model_dump(), "availability": SlotAvailability.UNAVAILABLE}
    )
    tournament = tournament.model_copy(
        update={"slots": (blocked_slot, *tournament.slots[1:])}
    )
    eligible = {match.id: frozenset(slot.id for slot in tournament.slots) for match in matches}

    result = solve_hard_feasible_schedule(
        tournament,
        matches,
        eligible,
        required_slot_by_match={matches[0].id: blocked.id},
    )

    assert result.status is SolverStatus.INFEASIBLE
    assert result.placements == ()


def test_rejects_a_missing_or_fabricated_match_graph_before_solving() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)[:-1]
    eligible = {match.id: frozenset(slot.id for slot in tournament.slots) for match in matches}

    result = solve_hard_feasible_schedule(tournament, matches, eligible)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.evidence_codes == (InfeasibilityCode.INVALID_MATCH_GRAPH,)
