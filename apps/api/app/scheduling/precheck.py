from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from enum import StrEnum
from uuid import UUID

from app.domain.common import DomainModel
from app.domain.matches import MatchDefinition
from app.domain.tournament import TournamentConfig
from app.domain.venues import SlotAvailability, VenueSlot
from app.scheduling.intervals import allocation_bounds_utc_minutes
from app.scheduling.pairings import generate_match_graph
from app.scheduling.qualification_paths import build_qualification_path_matrix


class FeasibilityIssueCode(StrEnum):
    INVALID_MATCH_GRAPH = "invalid_match_graph"
    PRESET_MISMATCH = "preset_mismatch"
    TIMEZONE_MISMATCH = "timezone_mismatch"
    INSUFFICIENT_CAPACITY = "insufficient_capacity"
    BLACKOUT_CAPACITY = "blackout_capacity"
    NO_ELIGIBLE_SLOT = "no_eligible_slot"
    CONFLICTING_PIN = "conflicting_pin"
    CHRONOLOGY_CONFLICT = "chronology_conflict"
    REST_CONFLICT = "rest_conflict"


class RemedyCode(StrEnum):
    RESTORE_MATCH_GRAPH = "restore_match_graph"
    CONFIRM_PRESET = "confirm_preset"
    USE_SHARED_TIMEZONE = "use_shared_timezone"
    ADD_VENUE_SLOTS = "add_venue_slots"
    CHANGE_BLACKOUTS = "change_blackouts"
    CHANGE_REQUIRED_PIN = "change_required_pin"
    EXTEND_TOURNAMENT_WINDOW = "extend_tournament_window"
    REDUCE_MINIMUM_REST = "reduce_minimum_rest"


class FeasibilityEvidence(DomainModel):
    code: FeasibilityIssueCode
    message: str


class RemedyCandidate(DomainModel):
    code: RemedyCode
    description: str


class PrecheckResult(DomainModel):
    can_solve: bool
    evidence: tuple[FeasibilityEvidence, ...]
    remedies: tuple[RemedyCandidate, ...]

    @property
    def evidence_codes(self) -> tuple[FeasibilityIssueCode, ...]:
        return tuple(item.code for item in self.evidence)

    @property
    def remedy_codes(self) -> tuple[RemedyCode, ...]:
        return tuple(item.code for item in self.remedies)


_MESSAGES = {
    FeasibilityIssueCode.INVALID_MATCH_GRAPH: "The fixed 15-match graph is incomplete or changed.",
    FeasibilityIssueCode.PRESET_MISMATCH: (
        "The allocation block does not match the selected preset."
    ),
    FeasibilityIssueCode.TIMEZONE_MISMATCH: "Both Version 1 venues must share one IANA timezone.",
    FeasibilityIssueCode.INSUFFICIENT_CAPACITY: "Fewer than 15 eligible venue slots are available.",
    FeasibilityIssueCode.BLACKOUT_CAPACITY: "Blackouts reduce available capacity below 15 slots.",
    FeasibilityIssueCode.NO_ELIGIBLE_SLOT: "At least one match has no eligible available slot.",
    FeasibilityIssueCode.CONFLICTING_PIN: (
        "A required pin is invalid or conflicts with another pin."
    ),
    FeasibilityIssueCode.CHRONOLOGY_CONFLICT: (
        "Available slots cannot preserve knockout chronology."
    ),
    FeasibilityIssueCode.REST_CONFLICT: "Available slots cannot satisfy every required rest path.",
}

_REMEDIES = {
    FeasibilityIssueCode.INVALID_MATCH_GRAPH: (
        RemedyCode.RESTORE_MATCH_GRAPH,
        "Restore the fixed Version 1 match graph.",
    ),
    FeasibilityIssueCode.PRESET_MISMATCH: (
        RemedyCode.CONFIRM_PRESET,
        "Reconfirm T10 or T20 and its allocation block.",
    ),
    FeasibilityIssueCode.TIMEZONE_MISMATCH: (
        RemedyCode.USE_SHARED_TIMEZONE,
        "Select two venues in one confirmed IANA timezone.",
    ),
    FeasibilityIssueCode.INSUFFICIENT_CAPACITY: (
        RemedyCode.ADD_VENUE_SLOTS,
        "Add eligible venue start times.",
    ),
    FeasibilityIssueCode.BLACKOUT_CAPACITY: (
        RemedyCode.CHANGE_BLACKOUTS,
        "Edit and reconfirm blackout periods or add slots.",
    ),
    FeasibilityIssueCode.NO_ELIGIBLE_SLOT: (
        RemedyCode.ADD_VENUE_SLOTS,
        "Add a slot eligible for the affected fixture.",
    ),
    FeasibilityIssueCode.CONFLICTING_PIN: (
        RemedyCode.CHANGE_REQUIRED_PIN,
        "Edit and reconfirm the required fixture pin.",
    ),
    FeasibilityIssueCode.CHRONOLOGY_CONFLICT: (
        RemedyCode.EXTEND_TOURNAMENT_WINDOW,
        "Add later knockout slots or extend the tournament window.",
    ),
    FeasibilityIssueCode.REST_CONFLICT: (
        RemedyCode.REDUCE_MINIMUM_REST,
        "Edit and reconfirm minimum rest or add later slots.",
    ),
}


def _precedes(
    predecessor: VenueSlot,
    successor: VenueSlot,
    allocation_minutes: int,
    rest_minutes: int = 0,
    different_local_day: bool = False,
) -> bool:
    _, predecessor_end = allocation_bounds_utc_minutes(predecessor, allocation_minutes)
    successor_start, _ = allocation_bounds_utc_minutes(successor, allocation_minutes)
    return predecessor_end + rest_minutes <= successor_start and (
        not different_local_day or predecessor.local_date != successor.local_date
    )


def run_pre_solver_checks(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
    eligible_slot_ids_by_match: Mapping[UUID, frozenset[UUID]],
    *,
    required_slot_by_match: Mapping[UUID, UUID] | None = None,
    minimum_rest_minutes: int = 0,
) -> PrecheckResult:
    issues: list[FeasibilityIssueCode] = []
    ordered_matches = tuple(sorted(matches, key=lambda match: match.sequence))
    graph_valid = ordered_matches == generate_match_graph(tournament)
    if not graph_valid:
        issues.append(FeasibilityIssueCode.INVALID_MATCH_GRAPH)
    if tournament.allocation_minutes != tournament.match_format_preset.allocation_minutes:
        issues.append(FeasibilityIssueCode.PRESET_MISMATCH)
    if len({venue.iana_time_zone for venue in tournament.venues}) != 1:
        issues.append(FeasibilityIssueCode.TIMEZONE_MISMATCH)

    slot_by_id = {slot.id: slot for slot in tournament.slots}
    raw_ids = {
        slot_id
        for match in ordered_matches
        for slot_id in eligible_slot_ids_by_match.get(match.id, frozenset())
        if slot_id in slot_by_id
    }
    available_ids = {
        slot_id
        for slot_id in raw_ids
        if slot_by_id[slot_id].availability is SlotAvailability.AVAILABLE
    }
    if len(available_ids) < 15:
        issue = (
            FeasibilityIssueCode.BLACKOUT_CAPACITY
            if len(raw_ids) >= 15
            else FeasibilityIssueCode.INSUFFICIENT_CAPACITY
        )
        issues.append(issue)

    candidates = {
        match.id: tuple(
            slot_by_id[slot_id]
            for slot_id in eligible_slot_ids_by_match.get(match.id, frozenset())
            if slot_id in available_ids
        )
        for match in ordered_matches
    }
    if any(not candidates[match.id] for match in ordered_matches):
        issues.append(FeasibilityIssueCode.NO_ELIGIBLE_SLOT)

    pins = required_slot_by_match or {}
    pin_counts = Counter(pins.values())
    invalid_pin = any(
        match_id not in candidates
        or slot_id not in {slot.id for slot in candidates.get(match_id, ())}
        or pin_counts[slot_id] > 1
        for match_id, slot_id in pins.items()
    )
    if invalid_pin:
        issues.append(FeasibilityIssueCode.CONFLICTING_PIN)

    if graph_valid and all(candidates[match.id] for match in ordered_matches):
        group_matches = ordered_matches[:12]
        semifinals = ordered_matches[12:14]
        final = ordered_matches[14]
        chronology_ok = all(
            any(
                all(
                    any(
                        _precedes(group_slot, semifinal_slot, tournament.allocation_minutes)
                        for group_slot in candidates[group_match.id]
                    )
                    for group_match in group_matches
                )
                for semifinal_slot in candidates[semifinal.id]
            )
            for semifinal in semifinals
        ) and any(
            all(
                any(
                    _precedes(semifinal_slot, final_slot, tournament.allocation_minutes)
                    for semifinal_slot in candidates[semifinal.id]
                )
                for semifinal in semifinals
            )
            for final_slot in candidates[final.id]
        )
        if not chronology_ok:
            issues.append(FeasibilityIssueCode.CHRONOLOGY_CONFLICT)

        path_matrix = build_qualification_path_matrix(tournament, ordered_matches)
        rest_edges = {
            (source_id, path.semifinal_match_id)
            for path in path_matrix.team_paths
            for source_id in path.source_group_match_ids
        }
        rest_edges.update(
            (path.semifinal_match_id, path.final_match_id) for path in path_matrix.final_paths
        )
        rest_ok = all(
            any(
                _precedes(
                    predecessor_slot,
                    successor_slot,
                    tournament.allocation_minutes,
                    minimum_rest_minutes,
                    different_local_day=True,
                )
                for predecessor_slot in candidates[predecessor_id]
                for successor_slot in candidates[successor_id]
            )
            for predecessor_id, successor_id in rest_edges
        )
        if not rest_ok:
            issues.append(FeasibilityIssueCode.REST_CONFLICT)

    unique_issues = tuple(dict.fromkeys(issues))
    evidence = tuple(
        FeasibilityEvidence(code=code, message=_MESSAGES[code]) for code in unique_issues
    )
    remedy_pairs = tuple(dict.fromkeys(_REMEDIES[code] for code in unique_issues))
    remedies = tuple(RemedyCandidate(code=code, description=text) for code, text in remedy_pairs)
    return PrecheckResult(can_solve=not evidence, evidence=evidence, remedies=remedies)
