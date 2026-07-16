from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.domain.audit import AgentProvenance, AuditEvent
from app.domain.matches import MatchDefinition
from app.domain.schedules import FixturePlacement, ScheduleDraft
from app.domain.venues import VenueSlot
from app.domain.weather import WeatherSnapshot
from pydantic import ValidationError
from tests.domain.factories import uuid7, valid_tournament


def test_uuid7_and_aware_utc_timestamps_are_required() -> None:
    with pytest.raises(ValidationError, match="UUIDv7"):
        AgentProvenance(
            provider="openai",
            model="gpt-5.6",
            decision_id=UUID("01890f3e-0001-4000-8000-000000000001"),
        )

    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        AuditEvent(
            id=uuid7(2),
            workspace_id=uuid7(3),
            tournament_id=uuid7(4),
            actor_type="organizer",
            event_type="schedule.requested",
            summary="Requested schedule generation",
            structured_payload={},
            occurred_at=datetime(2026, 9, 1),
        )


def test_venue_slot_requires_ordered_utc_interval() -> None:
    tournament = valid_tournament()
    slot = tournament.slots[0]

    with pytest.raises(ValidationError, match="after starts_at_utc"):
        VenueSlot.model_validate(slot.model_dump() | {"ends_at_utc": slot.starts_at_utc})


def test_match_definition_rejects_self_dependency() -> None:
    match_id = uuid7(70)
    with pytest.raises(ValidationError, match="depend on itself"):
        MatchDefinition(
            id=match_id,
            stage="semifinal",
            sequence=13,
            participant_a="A1",
            participant_b="B2",
            dependency_ids=(match_id,),
        )


def test_fixture_placement_rejects_individual_duration_override() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        FixturePlacement.model_validate(
            {
                "match_id": uuid7(80),
                "slot_id": uuid7(81),
                "venue_id": uuid7(82),
                "starts_at_utc": datetime(2026, 9, 1, tzinfo=UTC),
                "ends_at_utc": datetime(2026, 9, 1, tzinfo=UTC) + timedelta(hours=4),
                "duration_minutes": 90,
            }
        )


def test_schedule_draft_requires_15_unique_placements() -> None:
    tournament = valid_tournament()
    base = tournament.slots[0]
    placements = tuple(
        FixturePlacement(
            match_id=uuid7(200 + index),
            slot_id=uuid7(300 + index),
            venue_id=base.venue_id,
            starts_at_utc=base.starts_at_utc + timedelta(days=index),
            ends_at_utc=base.ends_at_utc + timedelta(days=index),
        )
        for index in range(15)
    )
    draft = ScheduleDraft(
        id=uuid7(90),
        tournament_revision=tournament.revision,
        constraint_revision=tournament.constraints.revision,
        profile="balanced",
        status="ready",
        placements=placements,
        metrics={},
        validation_report={"valid": True},
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert len(draft.placements) == 15

    with pytest.raises(ValidationError, match="15 placements"):
        ScheduleDraft.model_validate(draft.model_dump() | {"placements": placements[:-1]})
    with pytest.raises(ValidationError, match="unique match"):
        ScheduleDraft.model_validate(
            draft.model_dump() | {"placements": placements[:-1] + (placements[0],)}
        )


def test_weather_and_audit_contracts_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        WeatherSnapshot.model_validate(
            {
                "venue_id": uuid7(500),
                "mode": "deterministic",
                "issued_at": datetime(2026, 8, 1, tzinfo=UTC),
                "fetched_at": datetime(2026, 8, 1, tzinfo=UTC),
                "valid_hours": (),
                "quality": "complete",
                "provider_metadata": {},
                "secret_key": "must-not-pass",
            }
        )
