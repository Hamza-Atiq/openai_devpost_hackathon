from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.domain.matches import MatchDefinition
from app.domain.schedules import FixturePlacement
from app.domain.venues import SlotAvailability, VenueSlot
from app.scheduling.pairings import generate_match_graph
from app.validation.validator import validate_schedule
from app.validation.violations import ViolationCode
from tests.domain.factories import uuid7, valid_tournament

GENERATED_AT = datetime(2026, 7, 16, 9, tzinfo=UTC)


def _golden():
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    slot_indexes = (*range(0, 12, 2), *range(1, 12, 2), 12, 13, 14)
    placements = tuple(
        FixturePlacement(
            match_id=match.id,
            slot_id=tournament.slots[slot_index].id,
            venue_id=tournament.slots[slot_index].venue_id,
            starts_at_utc=tournament.slots[slot_index].starts_at_utc,
            ends_at_utc=tournament.slots[slot_index].starts_at_utc
            + timedelta(minutes=tournament.allocation_minutes),
        )
        for match, slot_index in zip(matches, slot_indexes, strict=True)
    )
    return tournament, matches, placements


def _at_slot(placement, slot, allocation_minutes):
    return FixturePlacement(
        match_id=placement.match_id,
        slot_id=slot.id,
        venue_id=slot.venue_id,
        starts_at_utc=slot.starts_at_utc,
        ends_at_utc=slot.starts_at_utc + timedelta(minutes=allocation_minutes),
    )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    (
        ("omission", ViolationCode.MISSING_MATCH),
        ("duplication", ViolationCode.DUPLICATE_MATCH),
        ("fabrication", ViolationCode.FABRICATED_MATCH),
        ("venue_overlap", ViolationCode.VENUE_OVERLAP),
        ("allocation_overflow", ViolationCode.ALLOCATION_OVERFLOW),
        ("blackout", ViolationCode.UNAVAILABLE_SLOT),
        ("team_local_day", ViolationCode.TEAM_LOCAL_DAY),
        ("chronology", ViolationCode.STAGE_CHRONOLOGY),
        ("qualification", ViolationCode.QUALIFICATION_PATH),
    ),
)
def test_seeded_invalid_schedule_is_rejected(mutation: str, expected: ViolationCode) -> None:
    tournament, matches, placements = _golden()

    if mutation == "omission":
        placements = placements[:-1]
    elif mutation == "duplication":
        placements = (*placements[:-1], placements[0])
    elif mutation == "fabrication":
        placements = (
            placements[0].model_copy(update={"match_id": uuid7(999)}),
            *placements[1:],
        )
    elif mutation == "venue_overlap":
        placements = (
            placements[0],
            _at_slot(placements[1], tournament.slots[0], tournament.allocation_minutes),
            *placements[2:],
        )
    elif mutation == "allocation_overflow":
        first_slot = tournament.slots[0].model_copy(
            update={"ends_at_utc": tournament.slots[0].starts_at_utc + timedelta(hours=3)}
        )
        tournament = tournament.model_copy(update={"slots": (first_slot, *tournament.slots[1:])})
    elif mutation == "blackout":
        first_slot = VenueSlot.model_validate(
            {**tournament.slots[0].model_dump(), "availability": SlotAvailability.UNAVAILABLE}
        )
        tournament = tournament.model_copy(update={"slots": (first_slot, *tournament.slots[1:])})
    elif mutation == "team_local_day":
        placements = (
            placements[0],
            _at_slot(placements[1], tournament.slots[1], tournament.allocation_minutes),
            *placements[2:],
        )
    elif mutation == "chronology":
        group_placement = _at_slot(
            placements[5], tournament.slots[12], tournament.allocation_minutes
        )
        semifinal_placement = _at_slot(
            placements[12], tournament.slots[10], tournament.allocation_minutes
        )
        placements = (
            *placements[:5],
            group_placement,
            *placements[6:12],
            semifinal_placement,
            *placements[13:],
        )
    elif mutation == "qualification":
        bad_semifinal = MatchDefinition.model_validate(
            {**matches[13].model_dump(), "participant_a": "A1", "participant_b": "B2"}
        )
        matches = (*matches[:13], bad_semifinal, *matches[14:])

    report = validate_schedule(
        tournament,
        matches,
        placements,
        generated_at=GENERATED_AT,
    )

    assert report.valid is False
    assert expected in report.violation_codes


@pytest.mark.parametrize("start_offset_hours", (0, 2))
def test_duplicate_interval_ids_and_partial_overlap_are_rejected(
    start_offset_hours: int,
) -> None:
    tournament, matches, placements = _golden()
    first_slot = tournament.slots[0]
    second_slot = tournament.slots[1].model_copy(
        update={
            "venue_id": first_slot.venue_id,
            "starts_at_utc": first_slot.starts_at_utc + timedelta(hours=start_offset_hours),
            "ends_at_utc": first_slot.ends_at_utc + timedelta(hours=start_offset_hours),
            "local_date": first_slot.local_date,
        }
    )
    tournament = tournament.model_copy(
        update={"slots": (first_slot, second_slot, *tournament.slots[2:])}
    )
    placements = (
        placements[0],
        _at_slot(placements[6], second_slot, tournament.allocation_minutes),
        *placements[1:6],
        *placements[7:],
    )

    report = validate_schedule(
        tournament,
        matches,
        placements,
        generated_at=GENERATED_AT,
    )

    assert report.valid is False
    assert ViolationCode.VENUE_OVERLAP in report.violation_codes


def test_minimum_rest_mutation_is_rejected() -> None:
    tournament, matches, placements = _golden()

    report = validate_schedule(
        tournament,
        matches,
        placements,
        generated_at=GENERATED_AT,
        minimum_rest_minutes=24 * 60,
    )

    assert report.valid is False
    assert ViolationCode.REST_VIOLATION in report.violation_codes
