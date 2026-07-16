from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.schedules import FixturePlacement
from app.domain.venues import SlotAvailability, VenueSlot
from app.scheduling.pairings import generate_match_graph
from app.scheduling.repair import RepairStatus, repair_schedule
from tests.domain.factories import uuid7, valid_tournament

GENERATED_AT = datetime(2026, 7, 16, 11, tzinfo=UTC)


def _baseline(tournament, matches):
    slot_indexes = (*range(0, 12, 2), *range(1, 12, 2), 12, 13, 14)
    return tuple(
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


def test_sequential_repair_locks_each_prior_optimum() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    baseline = _baseline(tournament, matches)
    blocked = tournament.slots[0]
    blocked_slot = VenueSlot.model_validate(
        {**blocked.model_dump(), "availability": SlotAvailability.UNAVAILABLE}
    )
    replacement = VenueSlot.model_validate(
        {
            **blocked.model_dump(),
            "id": uuid7(900),
            "availability": SlotAvailability.AVAILABLE,
        }
    )
    tournament = tournament.model_copy(
        update={"slots": (blocked_slot, *tournament.slots[1:], replacement)}
    )
    eligible = {placement.match_id: frozenset((placement.slot_id,)) for placement in baseline}
    eligible[baseline[0].match_id] = frozenset((blocked.id, replacement.id))

    result = repair_schedule(
        tournament,
        matches,
        baseline,
        eligible,
        generated_at=GENERATED_AT,
        quality_cost_by_placement={(baseline[0].match_id, replacement.id): 7},
    )

    assert result.status is RepairStatus.FEASIBLE
    assert result.validation_report is not None and result.validation_report.valid
    assert result.pass_optima.changed_count == 1
    assert result.pass_optima.movement_cost == 0
    assert result.pass_optima.quality_cost == 7
    assert result.changed_match_ids == (baseline[0].match_id,)
    assert len(result.preserved_match_ids) == 14
    assert (
        next(
            placement
            for placement in result.placements
            if placement.match_id == baseline[0].match_id
        ).slot_id
        == replacement.id
    )


def test_infeasible_repair_returns_no_draft_placements() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    baseline = _baseline(tournament, matches)
    eligible = {match.id: frozenset() for match in matches}

    result = repair_schedule(
        tournament,
        matches,
        baseline,
        eligible,
        generated_at=GENERATED_AT,
    )

    assert result.status is RepairStatus.INFEASIBLE
    assert result.placements == ()
    assert result.validation_report is None
