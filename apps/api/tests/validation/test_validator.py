from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.schedules import FixturePlacement
from app.domain.venues import VenueSlot
from app.scheduling.pairings import generate_match_graph
from app.validation.digests import placement_digest
from app.validation.validator import VALIDATOR_VERSION, validate_schedule
from app.validation.violations import ViolationCode

from tests.domain.factories import valid_tournament

GENERATED_AT = datetime(2026, 7, 16, 8, tzinfo=UTC)


def _valid_placements():
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


def test_valid_golden_schedule_produces_traceable_deterministic_report() -> None:
    tournament, matches, placements = _valid_placements()

    first = validate_schedule(
        tournament,
        matches,
        placements,
        generated_at=GENERATED_AT,
    )
    second = validate_schedule(
        tournament,
        matches,
        tuple(reversed(placements)),
        generated_at=GENERATED_AT,
    )

    assert first == second
    assert first.valid is True
    assert first.validator_version == VALIDATOR_VERSION
    assert first.generated_at == GENERATED_AT
    assert len(first.input_digest) == 64
    assert len(first.placement_digest) == 64
    assert first.violations == ()
    assert first.checks
    assert all(check.passed for check in first.checks)


def test_missing_and_duplicate_matches_are_rejected() -> None:
    tournament, matches, placements = _valid_placements()
    mutated = (*placements[:-1], placements[0])

    report = validate_schedule(
        tournament,
        matches,
        mutated,
        generated_at=GENERATED_AT,
    )

    assert report.valid is False
    assert ViolationCode.MISSING_MATCH in report.violation_codes
    assert ViolationCode.DUPLICATE_MATCH in report.violation_codes


def test_placement_digest_is_canonical_across_input_order() -> None:
    _, _, placements = _valid_placements()

    assert placement_digest(placements) == placement_digest(tuple(reversed(placements)))


def test_validator_has_no_dependency_on_solver_model_construction() -> None:
    source = Path("apps/api/app/validation/validator.py").read_text(encoding="utf-8")
    imported_modules = {
        node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)
    }

    assert "app.scheduling.model" not in imported_modules


def test_validator_rejects_parallel_matches_at_one_configured_start() -> None:
    tournament, matches, placements = _valid_placements()
    first_slot = tournament.slots[0]
    parallel_slot = VenueSlot.model_validate(
        {
            **first_slot.model_dump(),
            "id": "01890f3e-0001-7000-8000-000000009998",
            "venue_id": tournament.venues[1].id,
        }
    )
    tournament = tournament.model_copy(
        update={"slots": (*tournament.slots, parallel_slot)}
    )
    parallel_placement = FixturePlacement(
        match_id=matches[6].id,
        slot_id=parallel_slot.id,
        venue_id=parallel_slot.venue_id,
        starts_at_utc=parallel_slot.starts_at_utc,
        ends_at_utc=parallel_slot.ends_at_utc,
    )
    mutated = tuple(
        parallel_placement if item.match_id == matches[6].id else item
        for item in placements
    )

    report = validate_schedule(
        tournament, matches, mutated, generated_at=GENERATED_AT
    )

    assert ViolationCode.TOURNAMENT_CONCURRENCY in report.violation_codes
