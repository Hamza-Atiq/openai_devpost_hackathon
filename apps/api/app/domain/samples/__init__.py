from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field

from app.domain.common import DomainModel
from app.domain.constraints import ConstraintSet
from app.domain.teams import Group, Team
from app.domain.tournament import TournamentConfig
from app.domain.venues import Venue, VenueSlot

_SAMPLE_DIRECTORY = Path(__file__).parent


class SampleVenue(DomainModel):
    display_name: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=120)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class SampleSeed(DomainModel):
    sample_id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=160)
    match_format_preset: Literal["T20"]
    start_offset_days: int = Field(ge=1, le=5)
    window_days: int = Field(ge=7, le=16)
    iana_time_zone: str
    team_names: tuple[str, str, str, str, str, str, str, str]
    venues: tuple[SampleVenue, SampleVenue]
    available_day_offsets: tuple[int, ...] = Field(min_length=8, max_length=21)
    local_start_times: tuple[time, ...] = Field(min_length=2, max_length=4)
    dual_start_day_count: int = Field(ge=1, le=7)


def available_samples() -> tuple[str, ...]:
    return tuple(path.stem for path in sorted(_SAMPLE_DIRECTORY.glob("*.json")))


def load_sample(sample_id: str, *, reference_date: date | None = None) -> TournamentConfig:
    path = _SAMPLE_DIRECTORY / f"{sample_id}.json"
    if path.parent != _SAMPLE_DIRECTORY or not path.is_file():
        raise ValueError("unknown sample tournament")
    seed = SampleSeed.model_validate_json(path.read_text(encoding="utf-8"))
    if seed.sample_id != sample_id:
        raise ValueError("sample_id must match its filename")
    return _expand_seed(
        seed,
        sample_index=available_samples().index(sample_id) + 1,
        reference_date=reference_date or date.today(),
    )


def _uuid7(sample_index: int, entity_number: int) -> UUID:
    combined = sample_index * 10_000 + entity_number
    return UUID(f"01890f3e-0001-7000-8000-{combined:012x}")


def _expand_seed(
    seed: SampleSeed,
    *,
    sample_index: int,
    reference_date: date,
) -> TournamentConfig:
    group_ids = (_uuid7(sample_index, 1), _uuid7(sample_index, 2))
    teams = tuple(
        Team(
            id=_uuid7(sample_index, 10 + index),
            display_name=name,
            group_id=group_ids[index // 4],
        )
        for index, name in enumerate(seed.team_names)
    )
    groups = (
        Group(id=group_ids[0], code="A", team_ids=tuple(team.id for team in teams[:4])),
        Group(id=group_ids[1], code="B", team_ids=tuple(team.id for team in teams[4:])),
    )
    confirmed_at = datetime(2026, 7, 1, tzinfo=UTC)
    venues = tuple(
        Venue(
            id=_uuid7(sample_index, 30 + index),
            display_name=source.display_name,
            city=source.city,
            country_code=source.country_code,
            latitude=source.latitude,
            longitude=source.longitude,
            iana_time_zone=seed.iana_time_zone,
            geocoding_provider="sample",
            geocoding_reference=f"{seed.sample_id}:venue:{index + 1}",
            confirmed_at=confirmed_at,
        )
        for index, source in enumerate(seed.venues)
    )
    zone = ZoneInfo(seed.iana_time_zone)
    start_date = reference_date + timedelta(days=seed.start_offset_days)
    end_date = start_date + timedelta(days=seed.window_days - 1)
    slots: list[VenueSlot] = []
    for day_offset in seed.available_day_offsets:
        if day_offset >= seed.window_days:
            raise ValueError("sample available day offset must fall inside its window")
        available_date = start_date + timedelta(days=day_offset)
        local_times = (
            seed.local_start_times
            if day_offset < seed.dual_start_day_count
            else seed.local_start_times[:1]
        )
        for time_index, local_start_time in enumerate(local_times):
            local_start = datetime.combine(available_date, local_start_time, tzinfo=zone)
            starts_at_utc = local_start.astimezone(UTC)
            for venue_index, venue in enumerate(venues):
                entity_number = 100 + day_offset * 4 + time_index * 2 + venue_index
                slots.append(
                    VenueSlot(
                        id=_uuid7(sample_index, entity_number),
                        venue_id=venue.id,
                        starts_at_utc=starts_at_utc,
                        ends_at_utc=starts_at_utc + timedelta(minutes=240),
                        local_date=available_date,
                        availability="available",
                        source="organizer",
                    )
                )

    return TournamentConfig(
        id=_uuid7(sample_index, 50),
        name=seed.name,
        match_format_preset=seed.match_format_preset,
        allocation_minutes=240,
        start_date=start_date,
        end_date=end_date,
        status="draft_setup",
        time_zone_policy="shared",
        teams=teams,
        groups=groups,
        venues=venues,
        slots=tuple(slots),
        constraints=ConstraintSet(hard=(), soft=(), revision=0, confirmation_state="draft"),
        priorities={},
        revision=0,
    )
