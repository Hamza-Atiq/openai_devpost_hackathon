from __future__ import annotations

from datetime import date, time
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field

from app.domain.common import DomainModel
from app.domain.tournament import MatchFormatPreset, PrioritySettings, TournamentConfig


class SetupVenueInput(DomainModel):
    display_name: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=120)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    iana_time_zone: str = Field(min_length=1, max_length=80)


class TournamentSetupDraftInput(DomainModel):
    expected_revision: int = Field(ge=0)
    match_format_preset: MatchFormatPreset
    start_date: date
    end_date: date
    venues: tuple[SetupVenueInput, SetupVenueInput]
    weekday_start_times: tuple[time, ...] = Field(min_length=1, max_length=8)
    weekend_start_times: tuple[time, ...] = Field(min_length=1, max_length=8)
    blackout_dates: tuple[date, ...] = Field(default=(), max_length=21)
    minimum_rest_minutes: int = Field(default=0, ge=0, le=10_080)
    priorities: PrioritySettings = PrioritySettings()


class TournamentSetupState(DomainModel):
    weekday_start_times: tuple[time, ...]
    weekend_start_times: tuple[time, ...]
    blackout_dates: tuple[date, ...]
    minimum_rest_minutes: int
    save_state: Literal["saved"] = "saved"


class TournamentSetupView(TournamentConfig):
    setup_draft: TournamentSetupState


def setup_state_from_input(body: TournamentSetupDraftInput) -> TournamentSetupState:
    return TournamentSetupState(
        weekday_start_times=body.weekday_start_times,
        weekend_start_times=body.weekend_start_times,
        blackout_dates=body.blackout_dates,
        minimum_rest_minutes=body.minimum_rest_minutes,
    )


def setup_view(
    tournament: TournamentConfig,
    state: TournamentSetupState | None,
) -> TournamentSetupView:
    if state is None:
        available = tuple(
            slot
            for slot in tournament.slots
            if slot.availability.value == "available"
        )
        local_times = tuple(
            dict.fromkeys(
                slot.starts_at_utc.astimezone(
                    ZoneInfo(tournament.venues[0].iana_time_zone)
                ).time().replace(tzinfo=None)
                for slot in available
            )
        )
        fallback = local_times or (time(10, 0),)
        state = TournamentSetupState(
            weekday_start_times=fallback,
            weekend_start_times=fallback,
            blackout_dates=tuple(
                dict.fromkeys(
                    slot.local_date
                    for slot in tournament.slots
                    if slot.availability.value == "unavailable"
                )
            ),
            minimum_rest_minutes=0,
        )
    return TournamentSetupView.model_validate(
        {**tournament.model_dump(mode="python"), "setup_draft": state}
    )
