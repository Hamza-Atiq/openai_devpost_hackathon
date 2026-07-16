from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

from ortools.sat.python import cp_model

from app.domain.matches import MatchDefinition
from app.domain.venues import VenueSlot


def _utc_minute(value: datetime) -> int:
    return int(value.timestamp() // 60)


def allocation_bounds_utc_minutes(slot: VenueSlot, allocation_minutes: int) -> tuple[int, int]:
    start = _utc_minute(slot.starts_at_utc)
    return start, start + allocation_minutes


def add_venue_interval_constraints(
    model: cp_model.CpModel,
    placement: Mapping[tuple[UUID, UUID], cp_model.IntVar],
    matches: Sequence[MatchDefinition],
    slots: Sequence[VenueSlot],
    allocation_minutes: int,
) -> None:
    intervals_by_venue: dict[UUID, list[cp_model.IntervalVar]] = defaultdict(list)

    for match in matches:
        for slot in slots:
            start, end = allocation_bounds_utc_minutes(slot, allocation_minutes)
            is_present = placement[(match.id, slot.id)]
            interval = model.new_optional_fixed_size_interval_var(
                start,
                allocation_minutes,
                is_present,
                f"allocation_{match.sequence}_{slot.id}",
            )
            intervals_by_venue[slot.venue_id].append(interval)
            if end > _utc_minute(slot.ends_at_utc):
                model.add(is_present == 0)

    for intervals in intervals_by_venue.values():
        model.add_no_overlap(intervals)
