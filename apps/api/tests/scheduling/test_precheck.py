from __future__ import annotations

from app.domain.venues import SlotAvailability, Venue, VenueSlot
from app.scheduling.pairings import generate_match_graph
from app.scheduling.precheck import (
    FeasibilityIssueCode,
    RemedyCode,
    run_pre_solver_checks,
)

from tests.domain.factories import valid_tournament


def _all_slots_eligible(tournament, matches):
    slot_ids = frozenset(slot.id for slot in tournament.slots)
    return {match.id: slot_ids for match in matches}


def test_valid_inputs_pass_without_evidence_or_remedies() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)

    result = run_pre_solver_checks(tournament, matches, _all_slots_eligible(tournament, matches))

    assert result.can_solve is True
    assert result.evidence == ()
    assert result.remedies == ()


def test_insufficient_capacity_returns_stable_evidence_and_remedy() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    fourteen_slots = frozenset(slot.id for slot in tournament.slots[:14])
    eligible = {match.id: fourteen_slots for match in matches}

    result = run_pre_solver_checks(tournament, matches, eligible)

    assert result.can_solve is False
    assert FeasibilityIssueCode.INSUFFICIENT_CAPACITY in result.evidence_codes
    assert RemedyCode.ADD_VENUE_SLOTS in result.remedy_codes


def test_parallel_venue_rows_count_as_one_configured_start_opportunity() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    first = tournament.slots[0]
    slots = tuple(
        VenueSlot.model_validate(
            {
                **slot.model_dump(),
                "starts_at_utc": first.starts_at_utc,
                "ends_at_utc": first.ends_at_utc,
                "local_date": first.local_date,
            }
        )
        if index >= 14
        else slot
        for index, slot in enumerate(tournament.slots)
    )
    tournament = tournament.model_copy(update={"slots": slots})

    result = run_pre_solver_checks(
        tournament, matches, _all_slots_eligible(tournament, matches)
    )

    assert FeasibilityIssueCode.INSUFFICIENT_CAPACITY in result.evidence_codes


def test_blackouts_that_remove_capacity_are_identified_separately() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    blocked_ids = {slot.id for slot in tournament.slots[:2]}
    slots = tuple(
        VenueSlot.model_validate(
            {
                **slot.model_dump(),
                "availability": (
                    SlotAvailability.UNAVAILABLE if slot.id in blocked_ids else slot.availability
                ),
            }
        )
        for slot in tournament.slots
    )
    tournament = tournament.model_copy(update={"slots": slots})

    result = run_pre_solver_checks(tournament, matches, _all_slots_eligible(tournament, matches))

    assert FeasibilityIssueCode.BLACKOUT_CAPACITY in result.evidence_codes
    assert RemedyCode.CHANGE_BLACKOUTS in result.remedy_codes


def test_conflicting_required_pins_are_reported_without_relaxing_them() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    eligible = _all_slots_eligible(tournament, matches)
    pinned_slot_id = tournament.slots[0].id

    result = run_pre_solver_checks(
        tournament,
        matches,
        eligible,
        required_slot_by_match={matches[0].id: pinned_slot_id, matches[6].id: pinned_slot_id},
    )

    assert FeasibilityIssueCode.CONFLICTING_PIN in result.evidence_codes
    assert RemedyCode.CHANGE_REQUIRED_PIN in result.remedy_codes


def test_impossible_rest_and_chronology_have_distinct_evidence() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    eligible = _all_slots_eligible(tournament, matches)

    rest_result = run_pre_solver_checks(
        tournament,
        matches,
        eligible,
        minimum_rest_minutes=10 * 24 * 60,
    )
    chronology_eligible = dict(eligible)
    earliest = frozenset(slot.id for slot in tournament.slots[:2])
    later = frozenset(slot.id for slot in tournament.slots[2:])
    for match in matches[:12]:
        chronology_eligible[match.id] = later
    for match in matches[12:14]:
        chronology_eligible[match.id] = earliest
    chronology_result = run_pre_solver_checks(tournament, matches, chronology_eligible)

    assert FeasibilityIssueCode.REST_CONFLICT in rest_result.evidence_codes
    assert RemedyCode.REDUCE_MINIMUM_REST in rest_result.remedy_codes
    assert FeasibilityIssueCode.CHRONOLOGY_CONFLICT in chronology_result.evidence_codes
    assert RemedyCode.EXTEND_TOURNAMENT_WINDOW in chronology_result.remedy_codes


def test_preset_and_timezone_invariants_return_typed_evidence() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    mismatched_venue = Venue.model_validate(
        {**tournament.venues[1].model_dump(), "iana_time_zone": "UTC"}
    )
    invalid = tournament.model_copy(
        update={
            "allocation_minutes": 120,
            "venues": (tournament.venues[0], mismatched_venue),
        }
    )

    first = run_pre_solver_checks(invalid, matches, _all_slots_eligible(invalid, matches))
    second = run_pre_solver_checks(invalid, matches, _all_slots_eligible(invalid, matches))

    assert first == second
    assert FeasibilityIssueCode.PRESET_MISMATCH in first.evidence_codes
    assert FeasibilityIssueCode.TIMEZONE_MISMATCH in first.evidence_codes
    assert RemedyCode.CONFIRM_PRESET in first.remedy_codes
    assert RemedyCode.USE_SHARED_TIMEZONE in first.remedy_codes
