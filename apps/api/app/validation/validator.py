from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timedelta
from itertools import combinations

from app.domain.matches import MatchDefinition, MatchStage
from app.domain.schedules import FixturePlacement
from app.domain.tournament import TournamentConfig
from app.domain.venues import SlotAvailability
from app.scheduling.qualification_paths import build_qualification_path_matrix
from app.validation.digests import placement_digest, validation_input_digest
from app.validation.violations import (
    IndependentValidationReport,
    ValidationCheck,
    ValidationViolation,
    ViolationCode,
)

VALIDATOR_VERSION = "1.0.0"


def _violation(
    code: ViolationCode,
    message: str,
    *matches: MatchDefinition | FixturePlacement,
) -> ValidationViolation:
    return ValidationViolation(
        code=code,
        message=message,
        match_ids=tuple(
            item.id if isinstance(item, MatchDefinition) else item.match_id for item in matches
        ),
    )


def _validate_match_graph(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
) -> list[ValidationViolation]:
    ordered = tuple(sorted(matches, key=lambda item: item.sequence))
    stages = Counter(match.stage for match in ordered)
    valid = (
        len(ordered) == 15
        and len({match.id for match in ordered}) == 15
        and [match.sequence for match in ordered] == list(range(1, 16))
        and stages == {MatchStage.GROUP: 12, MatchStage.SEMIFINAL: 2, MatchStage.FINAL: 1}
    )
    group_matches = tuple(match for match in ordered if match.stage is MatchStage.GROUP)
    actual_pairs = {
        frozenset((match.participant_a, match.participant_b)) for match in group_matches
    }
    expected_pairs = {
        frozenset((str(first), str(second)))
        for group in tournament.groups
        for first, second in combinations(group.team_ids, 2)
    }
    semifinals = tuple(match for match in ordered if match.stage is MatchStage.SEMIFINAL)
    semifinal_pairs = {(match.participant_a, match.participant_b) for match in semifinals}
    finals = tuple(match for match in ordered if match.stage is MatchStage.FINAL)
    valid = valid and actual_pairs == expected_pairs
    valid = valid and semifinal_pairs == {("A1", "B2"), ("B1", "A2")}
    valid = (
        valid
        and len(finals) == 1
        and (
            finals[0].participant_a,
            finals[0].participant_b,
        )
        == ("SF1 Winner", "SF2 Winner")
    )
    return (
        [] if valid else [_violation(ViolationCode.INVALID_MATCH_GRAPH, "Match graph is invalid.")]
    )


def _validate_placement_membership(
    matches: Sequence[MatchDefinition],
    placements: Sequence[FixturePlacement],
) -> list[ValidationViolation]:
    violations: list[ValidationViolation] = []
    expected = {match.id for match in matches}
    counts = Counter(placement.match_id for placement in placements)
    if expected - set(counts):
        violations.append(_violation(ViolationCode.MISSING_MATCH, "A required match is missing."))
    if any(count > 1 for count in counts.values()):
        violations.append(
            _violation(ViolationCode.DUPLICATE_MATCH, "A match is placed more than once.")
        )
    if set(counts) - expected:
        violations.append(
            _violation(ViolationCode.FABRICATED_MATCH, "An unknown match was placed.")
        )
    return violations


def _validate_slots(
    tournament: TournamentConfig,
    placements: Sequence[FixturePlacement],
) -> list[ValidationViolation]:
    violations: list[ValidationViolation] = []
    slot_by_id = {slot.id: slot for slot in tournament.slots}
    for placement in placements:
        slot = slot_by_id.get(placement.slot_id)
        if slot is None:
            violations.append(
                _violation(ViolationCode.UNKNOWN_SLOT, "Placement uses an unknown slot.", placement)
            )
            continue
        if slot.availability is not SlotAvailability.AVAILABLE:
            violations.append(
                _violation(
                    ViolationCode.UNAVAILABLE_SLOT, "Placement uses an unavailable slot.", placement
                )
            )
        expected_end = placement.starts_at_utc + timedelta(minutes=tournament.allocation_minutes)
        if (
            placement.venue_id != slot.venue_id
            or placement.starts_at_utc != slot.starts_at_utc
            or placement.ends_at_utc != expected_end
        ):
            violations.append(
                _violation(
                    ViolationCode.PLACEMENT_MISMATCH,
                    "Placement does not match its slot.",
                    placement,
                )
            )
        if expected_end > slot.ends_at_utc:
            violations.append(
                _violation(
                    ViolationCode.ALLOCATION_OVERFLOW, "Allocation exceeds availability.", placement
                )
            )

    known = tuple(placement for placement in placements if placement.slot_id in slot_by_id)
    for first, second in combinations(known, 2):
        if first.venue_id == second.venue_id and (
            first.starts_at_utc < second.ends_at_utc and second.starts_at_utc < first.ends_at_utc
        ):
            violations.append(
                _violation(ViolationCode.VENUE_OVERLAP, "Venue allocations overlap.", first, second)
            )
    return violations


def _validate_chronology_and_teams(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
    placements: Sequence[FixturePlacement],
    minimum_rest_minutes: int,
) -> list[ValidationViolation]:
    violations: list[ValidationViolation] = []
    match_by_id = {match.id: match for match in matches}
    placement_by_match = {
        placement.match_id: placement
        for placement in placements
        if placement.match_id in match_by_id
    }
    if len(placement_by_match) != 15:
        return violations
    slot_by_id = {slot.id: slot for slot in tournament.slots}
    group_matches = tuple(match for match in matches if match.stage is MatchStage.GROUP)
    semifinals = tuple(match for match in matches if match.stage is MatchStage.SEMIFINAL)
    final = next((match for match in matches if match.stage is MatchStage.FINAL), None)
    if len(group_matches) != 12 or len(semifinals) != 2 or final is None:
        return violations

    rest = timedelta(minutes=minimum_rest_minutes)
    for first, second in combinations(group_matches, 2):
        if {first.participant_a, first.participant_b}.isdisjoint(
            (second.participant_a, second.participant_b)
        ):
            continue
        first_placement = placement_by_match[first.id]
        second_placement = placement_by_match[second.id]
        first_slot = slot_by_id.get(first_placement.slot_id)
        second_slot = slot_by_id.get(second_placement.slot_id)
        if first_slot and second_slot and first_slot.local_date == second_slot.local_date:
            violations.append(
                _violation(
                    ViolationCode.TEAM_LOCAL_DAY,
                    "Team plays twice on one local day.",
                    first,
                    second,
                )
            )
        ordered = sorted((first_placement, second_placement), key=lambda item: item.starts_at_utc)
        if ordered[0].ends_at_utc + rest > ordered[1].starts_at_utc:
            violations.append(
                _violation(
                    ViolationCode.REST_VIOLATION, "Team rest is insufficient.", first, second
                )
            )

    latest_group_end = max(placement_by_match[match.id].ends_at_utc for match in group_matches)
    earliest_semifinal_start = min(
        placement_by_match[match.id].starts_at_utc for match in semifinals
    )
    latest_semifinal_end = max(placement_by_match[match.id].ends_at_utc for match in semifinals)
    final_placement = placement_by_match[final.id]
    if (
        latest_group_end > earliest_semifinal_start
        or latest_semifinal_end > final_placement.starts_at_utc
    ):
        violations.append(
            _violation(ViolationCode.STAGE_CHRONOLOGY, "Knockout chronology is invalid.")
        )

    try:
        matrix = build_qualification_path_matrix(tournament, matches)
    except ValueError:
        violations.append(
            _violation(ViolationCode.QUALIFICATION_PATH, "Qualification paths are invalid.")
        )
        return violations
    path_edges = {
        (source_id, path.semifinal_match_id)
        for path in matrix.team_paths
        for source_id in path.source_group_match_ids
    }
    path_edges.update((path.semifinal_match_id, path.final_match_id) for path in matrix.final_paths)
    for predecessor_id, successor_id in path_edges:
        predecessor = placement_by_match[predecessor_id]
        successor = placement_by_match[successor_id]
        predecessor_slot = slot_by_id.get(predecessor.slot_id)
        successor_slot = slot_by_id.get(successor.slot_id)
        if (
            predecessor.ends_at_utc + rest > successor.starts_at_utc
            or predecessor_slot is None
            or successor_slot is None
            or predecessor_slot.local_date == successor_slot.local_date
        ):
            violations.append(
                _violation(ViolationCode.QUALIFICATION_PATH, "A knockout rest path is invalid.")
            )
            break
    return violations


def validate_schedule(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
    placements: Sequence[FixturePlacement],
    *,
    generated_at: datetime,
    minimum_rest_minutes: int = 0,
) -> IndependentValidationReport:
    violations = (
        _validate_match_graph(tournament, matches)
        + _validate_placement_membership(matches, placements)
        + _validate_slots(tournament, placements)
        + _validate_chronology_and_teams(
            tournament,
            matches,
            placements,
            minimum_rest_minutes,
        )
    )
    categories = {
        "format": {ViolationCode.INVALID_MATCH_GRAPH},
        "completeness": {
            ViolationCode.MISSING_MATCH,
            ViolationCode.DUPLICATE_MATCH,
            ViolationCode.FABRICATED_MATCH,
        },
        "placements": {
            ViolationCode.UNKNOWN_SLOT,
            ViolationCode.UNAVAILABLE_SLOT,
            ViolationCode.PLACEMENT_MISMATCH,
            ViolationCode.ALLOCATION_OVERFLOW,
            ViolationCode.VENUE_OVERLAP,
        },
        "teams_and_chronology": {
            ViolationCode.TEAM_OVERLAP,
            ViolationCode.TEAM_LOCAL_DAY,
            ViolationCode.REST_VIOLATION,
            ViolationCode.STAGE_CHRONOLOGY,
            ViolationCode.QUALIFICATION_PATH,
        },
    }
    violation_codes = {violation.code for violation in violations}
    checks = tuple(
        ValidationCheck(name=name, passed=not bool(codes & violation_codes))
        for name, codes in categories.items()
    )
    return IndependentValidationReport(
        valid=not violations,
        input_digest=validation_input_digest(tournament, matches, minimum_rest_minutes),
        placement_digest=placement_digest(placements),
        validator_version=VALIDATOR_VERSION,
        checks=checks,
        violations=tuple(violations),
        generated_at=generated_at,
    )
