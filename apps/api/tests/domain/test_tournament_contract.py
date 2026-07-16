from __future__ import annotations

from datetime import date

import pytest
from app.domain.tournament import TournamentConfig
from app.domain.venues import Venue
from pydantic import ValidationError
from tests.domain.factories import valid_tournament, valid_tournament_payload


def test_valid_t20_tournament_is_frozen_and_uses_240_minutes() -> None:
    tournament = valid_tournament()

    assert tournament.schema_version == 1
    assert tournament.match_format_preset == "T20"
    assert tournament.allocation_minutes == 240
    with pytest.raises(ValidationError, match="frozen"):
        tournament.name = "Changed"  # type: ignore[misc]


def test_t10_uses_120_minutes_and_schema_version_is_fixed() -> None:
    payload = valid_tournament_payload() | {
        "match_format_preset": "T10",
        "allocation_minutes": 120,
    }

    tournament = TournamentConfig.model_validate(payload)

    assert tournament.allocation_minutes == 120
    with pytest.raises(ValidationError, match="schema_version"):
        TournamentConfig.model_validate(payload | {"schema_version": 2})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("match_format_preset", "ODI", "match_format_preset"),
        ("allocation_minutes", 120, "allocation_minutes"),
        ("end_date", date(2026, 9, 6), "7 and 21"),
        ("end_date", date(2026, 9, 22), "7 and 21"),
    ],
)
def test_tournament_rejects_unsupported_format_duration_and_window(
    field: str, value: object, message: str
) -> None:
    payload = valid_tournament_payload() | {field: value}

    with pytest.raises(ValidationError, match=message):
        TournamentConfig.model_validate(payload)


def test_tournament_rejects_unknown_fields_and_invalid_cardinality() -> None:
    payload = valid_tournament_payload()

    with pytest.raises(ValidationError, match="extra_forbidden"):
        TournamentConfig.model_validate(payload | {"format_notes": "custom duration"})
    with pytest.raises(ValidationError, match="8 teams"):
        TournamentConfig.model_validate(payload | {"teams": payload["teams"][:-1]})  # type: ignore[index]
    with pytest.raises(ValidationError, match="2 venues"):
        TournamentConfig.model_validate(payload | {"venues": payload["venues"][:1]})  # type: ignore[index]


def test_group_membership_must_match_each_team_assignment() -> None:
    payload = valid_tournament_payload()
    groups = payload["groups"]
    shortened_group = groups[0].model_copy(  # type: ignore[index,union-attr]
        update={"team_ids": groups[0].team_ids[:-1]}  # type: ignore[index,union-attr]
    )
    payload["groups"] = (shortened_group, groups[1])  # type: ignore[index]

    with pytest.raises(ValidationError, match="four teams"):
        TournamentConfig.model_validate(payload)


def test_both_venues_must_use_the_same_valid_iana_timezone() -> None:
    payload = valid_tournament_payload()
    first, second = payload["venues"]  # type: ignore[misc]
    payload["venues"] = (first, second.model_copy(update={"iana_time_zone": "Europe/London"}))

    with pytest.raises(ValidationError, match="same IANA timezone"):
        TournamentConfig.model_validate(payload)

    invalid_venue = first.model_dump() | {"iana_time_zone": "Mars/Olympus"}
    with pytest.raises(ValidationError, match="IANA timezone"):
        Venue.model_validate(invalid_venue)
