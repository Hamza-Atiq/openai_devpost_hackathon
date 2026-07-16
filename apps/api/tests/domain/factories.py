from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.domain.constraints import ConstraintSet
from app.domain.teams import Group, Team
from app.domain.tournament import TournamentConfig
from app.domain.venues import Venue, VenueSlot


def uuid7(number: int) -> UUID:
    return UUID(f"01890f3e-0001-7000-8000-{number:012x}")


def valid_tournament_payload() -> dict[str, object]:
    group_ids = (uuid7(1), uuid7(2))
    teams = tuple(
        Team(id=uuid7(10 + index), display_name=f"Team {index + 1}", group_id=group_ids[index // 4])
        for index in range(8)
    )
    groups = (
        Group(id=group_ids[0], code="A", team_ids=tuple(team.id for team in teams[:4])),
        Group(id=group_ids[1], code="B", team_ids=tuple(team.id for team in teams[4:])),
    )
    venues = (
        Venue(
            id=uuid7(30),
            display_name="North Ground",
            city="Lahore",
            country_code="PK",
            latitude=31.5204,
            longitude=74.3587,
            iana_time_zone="Asia/Karachi",
            geocoding_provider="manual",
            confirmed_at=datetime(2026, 7, 1, tzinfo=UTC),
        ),
        Venue(
            id=uuid7(31),
            display_name="South Ground",
            city="Lahore",
            country_code="PK",
            latitude=31.5000,
            longitude=74.3200,
            iana_time_zone="Asia/Karachi",
            geocoding_provider="manual",
            confirmed_at=datetime(2026, 7, 1, tzinfo=UTC),
        ),
    )
    starts_at = datetime(2026, 9, 1, 4, tzinfo=UTC)
    slots = tuple(
        VenueSlot(
            id=uuid7(100 + index),
            venue_id=venues[index % 2].id,
            starts_at_utc=starts_at + timedelta(days=index // 2, hours=(index % 2) * 5),
            ends_at_utc=starts_at
            + timedelta(days=index // 2, hours=(index % 2) * 5 + 4),
            local_date=date(2026, 9, 1) + timedelta(days=index // 2),
            availability="available",
            source="organizer",
        )
        for index in range(16)
    )
    return {
        "id": uuid7(50),
        "name": "CrickOps Cup",
        "match_format_preset": "T20",
        "allocation_minutes": 240,
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 10),
        "status": "draft",
        "time_zone_policy": "shared",
        "teams": teams,
        "groups": groups,
        "venues": venues,
        "slots": slots,
        "constraints": ConstraintSet(hard=(), soft=(), revision=0, confirmation_state="draft"),
        "priorities": {},
        "revision": 0,
    }


def valid_tournament() -> TournamentConfig:
    return TournamentConfig.model_validate(valid_tournament_payload())
