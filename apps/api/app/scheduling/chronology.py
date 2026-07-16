from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from ortools.sat.python import cp_model

from app.domain.matches import MatchDefinition, MatchStage
from app.domain.tournament import TournamentConfig
from app.domain.venues import VenueSlot
from app.scheduling.intervals import allocation_bounds_utc_minutes
from app.scheduling.qualification_paths import build_qualification_path_matrix


def _forbid_pair(
    model: cp_model.CpModel,
    placement: Mapping[tuple[UUID, UUID], cp_model.IntVar],
    first_match_id: UUID,
    first_slot_id: UUID,
    second_match_id: UUID,
    second_slot_id: UUID,
) -> None:
    model.add(
        placement[(first_match_id, first_slot_id)]
        + placement[(second_match_id, second_slot_id)]
        <= 1
    )


def _has_required_gap(
    first_slot: VenueSlot,
    second_slot: VenueSlot,
    allocation_minutes: int,
    rest_minutes: int,
) -> bool:
    first_start, first_end = allocation_bounds_utc_minutes(first_slot, allocation_minutes)
    second_start, second_end = allocation_bounds_utc_minutes(second_slot, allocation_minutes)
    return first_end + rest_minutes <= second_start or second_end + rest_minutes <= first_start


def _add_known_team_constraints(
    model: cp_model.CpModel,
    placement: Mapping[tuple[UUID, UUID], cp_model.IntVar],
    group_matches: Sequence[MatchDefinition],
    candidate_slots: Mapping[UUID, Sequence[VenueSlot]],
    allocation_minutes: int,
    rest_minutes: int,
) -> None:
    for index, first in enumerate(group_matches):
        first_participants = {first.participant_a, first.participant_b}
        for second in group_matches[index + 1 :]:
            if first_participants.isdisjoint((second.participant_a, second.participant_b)):
                continue
            for first_slot in candidate_slots[first.id]:
                for second_slot in candidate_slots[second.id]:
                    same_local_day = first_slot.local_date == second_slot.local_date
                    has_rest = _has_required_gap(
                        first_slot,
                        second_slot,
                        allocation_minutes,
                        rest_minutes,
                    )
                    if same_local_day or not has_rest:
                        _forbid_pair(
                            model,
                            placement,
                            first.id,
                            first_slot.id,
                            second.id,
                            second_slot.id,
                        )


def _add_directed_precedence(
    model: cp_model.CpModel,
    placement: Mapping[tuple[UUID, UUID], cp_model.IntVar],
    predecessor_id: UUID,
    successor_id: UUID,
    predecessor_slots: Sequence[VenueSlot],
    successor_slots: Sequence[VenueSlot],
    allocation_minutes: int,
    rest_minutes: int = 0,
    prohibit_same_local_day: bool = False,
) -> None:
    for predecessor_slot in predecessor_slots:
        _, predecessor_end = allocation_bounds_utc_minutes(
            predecessor_slot, allocation_minutes
        )
        for successor_slot in successor_slots:
            successor_start, _ = allocation_bounds_utc_minutes(successor_slot, allocation_minutes)
            same_local_day = predecessor_slot.local_date == successor_slot.local_date
            if successor_start < predecessor_end + rest_minutes or (
                prohibit_same_local_day and same_local_day
            ):
                _forbid_pair(
                    model,
                    placement,
                    predecessor_id,
                    predecessor_slot.id,
                    successor_id,
                    successor_slot.id,
                )


def add_chronology_constraints(
    model: cp_model.CpModel,
    placement: Mapping[tuple[UUID, UUID], cp_model.IntVar],
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
    slots: Sequence[VenueSlot],
    eligible_slot_ids_by_match: Mapping[UUID, frozenset[UUID]],
    minimum_rest_minutes: int,
) -> None:
    slot_by_id = {slot.id: slot for slot in slots}
    candidate_slots = {
        match.id: tuple(
            slot_by_id[slot_id]
            for slot_id in eligible_slot_ids_by_match.get(match.id, frozenset())
            if slot_id in slot_by_id
        )
        for match in matches
    }
    group_matches = tuple(match for match in matches if match.stage is MatchStage.GROUP)
    semifinals = tuple(match for match in matches if match.stage is MatchStage.SEMIFINAL)
    final = next(match for match in matches if match.stage is MatchStage.FINAL)

    _add_known_team_constraints(
        model,
        placement,
        group_matches,
        candidate_slots,
        tournament.allocation_minutes,
        minimum_rest_minutes,
    )

    for group_match in group_matches:
        for semifinal in semifinals:
            _add_directed_precedence(
                model,
                placement,
                group_match.id,
                semifinal.id,
                candidate_slots[group_match.id],
                candidate_slots[semifinal.id],
                tournament.allocation_minutes,
            )

    path_matrix = build_qualification_path_matrix(tournament, matches)
    rest_edges = {
        (group_match_id, path.semifinal_match_id)
        for path in path_matrix.team_paths
        for group_match_id in path.source_group_match_ids
    }
    for group_match_id, semifinal_id in rest_edges:
        _add_directed_precedence(
            model,
            placement,
            group_match_id,
            semifinal_id,
            candidate_slots[group_match_id],
            candidate_slots[semifinal_id],
            tournament.allocation_minutes,
            minimum_rest_minutes,
            prohibit_same_local_day=True,
        )

    for semifinal in semifinals:
        _add_directed_precedence(
            model,
            placement,
            semifinal.id,
            final.id,
            candidate_slots[semifinal.id],
            candidate_slots[final.id],
            tournament.allocation_minutes,
            minimum_rest_minutes,
            prohibit_same_local_day=True,
        )
