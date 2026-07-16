from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from app.domain.schedules import FixturePlacement
from app.domain.tournament import TournamentConfig

PlacementCosts = dict[tuple[UUID, UUID], int]


def changed_count_costs(
    tournament: TournamentConfig,
    baseline: Sequence[FixturePlacement],
) -> PlacementCosts:
    baseline_slot = {placement.match_id: placement.slot_id for placement in baseline}
    return {
        (match_id, slot.id): int(slot.id != slot_id)
        for match_id, slot_id in baseline_slot.items()
        for slot in tournament.slots
    }


def movement_costs(
    tournament: TournamentConfig,
    baseline: Sequence[FixturePlacement],
) -> PlacementCosts:
    costs: PlacementCosts = {}
    for placement in baseline:
        for slot in tournament.slots:
            movement_minutes = abs(
                int((slot.starts_at_utc - placement.starts_at_utc).total_seconds() // 60)
            )
            venue_change = (
                tournament.allocation_minutes if slot.venue_id != placement.venue_id else 0
            )
            costs[(placement.match_id, slot.id)] = movement_minutes + venue_change
    return costs


def bounded_quality_costs(
    tournament: TournamentConfig,
    baseline: Sequence[FixturePlacement],
    supplied: Mapping[tuple[UUID, UUID], int] | None,
) -> PlacementCosts:
    supplied = supplied or {}
    if any(value < 0 or value > 1000 for value in supplied.values()):
        raise ValueError("quality costs must be between 0 and 1000")
    return {
        (placement.match_id, slot.id): supplied.get((placement.match_id, slot.id), 0)
        for placement in baseline
        for slot in tournament.slots
    }
