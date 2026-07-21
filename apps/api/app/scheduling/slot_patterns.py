from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.api.setup_models import TournamentSetupDraftInput
from app.domain.constraints import ConfirmationState, ConstraintSet
from app.domain.teams import Group, Team
from app.domain.tournament import TournamentConfig, TournamentStatus
from app.domain.venues import SlotAvailability, SlotSource, Venue, VenueSlot


def _uuid7() -> UUID:
    raw = bytearray(uuid4().bytes)
    raw[6] = (raw[6] & 0x0F) | 0x70
    raw[8] = (raw[8] & 0x3F) | 0x80
    return UUID(bytes=bytes(raw))


def _dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def expand_slot_patterns(
    tournament: TournamentConfig,
    body: TournamentSetupDraftInput,
    *,
    now: datetime,
) -> TournamentConfig:
    venues = tuple(
        Venue(
            id=tournament.venues[index].id,
            display_name=source.display_name,
            city=source.city,
            country_code=source.country_code,
            latitude=source.latitude,
            longitude=source.longitude,
            iana_time_zone=source.iana_time_zone,
            geocoding_provider="manual",
            geocoding_reference=None,
            confirmed_at=now,
        )
        for index, source in enumerate(body.venues)
    )
    zone = ZoneInfo(venues[0].iana_time_zone)
    blackout_dates = set(body.blackout_dates)
    slots: list[VenueSlot] = []
    for local_date in _dates(body.start_date, body.end_date):
        starts = (
            body.weekend_start_times if local_date.weekday() >= 5 else body.weekday_start_times
        )
        for local_time in starts:
            starts_at = datetime.combine(local_date, local_time, tzinfo=zone).astimezone(UTC)
            for venue in venues:
                blacked_out = local_date in blackout_dates
                slots.append(
                    VenueSlot(
                        id=_uuid7(),
                        venue_id=venue.id,
                        starts_at_utc=starts_at,
                        ends_at_utc=starts_at
                        + timedelta(minutes=body.match_format_preset.allocation_minutes),
                        local_date=local_date,
                        availability=(
                            SlotAvailability.UNAVAILABLE
                            if blacked_out
                            else SlotAvailability.AVAILABLE
                        ),
                        source=SlotSource.BLACKOUT if blacked_out else SlotSource.ORGANIZER,
                    )
                )

    constraints = ConstraintSet(
        hard=tournament.constraints.hard,
        soft=tournament.constraints.soft,
        revision=tournament.constraints.revision + 1,
        confirmation_state=ConfirmationState.DRAFT,
        confirmed_at=None,
    )
    teams = (
        tuple(Team.model_validate(team.model_dump(mode="python")) for team in body.teams)
        if body.teams is not None
        else tournament.teams
    )
    groups = tuple(
        Group(
            id=group.id,
            code=group.code,
            team_ids=tuple(team.id for team in teams if team.group_id == group.id),
        )
        for group in tournament.groups
    )
    return TournamentConfig.model_validate(
        {
            **tournament.model_dump(mode="python"),
            "match_format_preset": body.match_format_preset,
            "allocation_minutes": body.match_format_preset.allocation_minutes,
            "start_date": body.start_date,
            "end_date": body.end_date,
            "status": TournamentStatus.AWAITING_CONSTRAINT_CONFIRMATION,
            "teams": teams,
            "groups": groups,
            "venues": venues,
            "slots": tuple(slots),
            "constraints": constraints,
            "priorities": body.priorities,
            "revision": tournament.revision + 1,
        }
    )
