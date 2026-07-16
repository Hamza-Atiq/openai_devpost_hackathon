from __future__ import annotations

from datetime import date
from enum import StrEnum
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from app.domain.common import UUID7, DomainModel
from app.domain.constraints import ConstraintSet
from app.domain.teams import Group, Team
from app.domain.venues import Venue, VenueSlot


class MatchFormatPreset(StrEnum):
    T10 = "T10"
    T20 = "T20"

    @property
    def allocation_minutes(self) -> int:
        return 120 if self is MatchFormatPreset.T10 else 240


class TournamentStatus(StrEnum):
    DRAFT_SETUP = "draft_setup"
    AWAITING_CONSTRAINT_CONFIRMATION = "awaiting_constraint_confirmation"
    READY_TO_SCHEDULE = "ready_to_schedule"
    OPTIONS_READY = "options_ready"
    OFFICIAL_SCHEDULE = "official_schedule"
    RECOVERY_DRAFT = "recovery_draft"


class TimeZonePolicy(StrEnum):
    SHARED = "shared"


class PrioritySettings(DomainModel):
    minimize_weather_risk: bool = True
    maximize_fair_rest: bool = True
    balance_venue_allocation: bool = True
    prefer_selected_time_slots: bool = True
    minimize_schedule_changes: bool = True


class TournamentConfig(DomainModel):
    id: UUID7
    name: str = Field(min_length=1, max_length=160)
    match_format_preset: MatchFormatPreset
    allocation_minutes: int
    start_date: date
    end_date: date
    status: TournamentStatus
    time_zone_policy: TimeZonePolicy
    teams: tuple[Team, ...]
    groups: tuple[Group, ...]
    venues: tuple[Venue, ...]
    slots: tuple[VenueSlot, ...]
    constraints: ConstraintSet
    priorities: PrioritySettings
    revision: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_version_one_boundaries(self) -> TournamentConfig:
        window_days = (self.end_date - self.start_date).days + 1
        if not 7 <= window_days <= 21:
            raise ValueError("tournament window must be between 7 and 21 calendar days")
        if self.allocation_minutes != self.match_format_preset.allocation_minutes:
            raise ValueError("allocation_minutes must match match_format_preset")
        if len(self.teams) != 8:
            raise ValueError("Version 1 requires exactly 8 teams")
        if len(self.groups) != 2:
            raise ValueError("Version 1 requires exactly 2 groups")
        if len(self.venues) != 2:
            raise ValueError("Version 1 requires exactly 2 venues")

        self._validate_unique_ids()
        self._validate_groups()
        self._validate_venues_and_slots()
        return self

    def _validate_unique_ids(self) -> None:
        for label, values in (
            ("team", self.teams),
            ("group", self.groups),
            ("venue", self.venues),
            ("slot", self.slots),
        ):
            identifiers = tuple(value.id for value in values)
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f"{label} identifiers must be unique")

    def _validate_groups(self) -> None:
        if {group.code for group in self.groups} != {"A", "B"}:
            raise ValueError("groups must use codes A and B")
        group_by_id = {group.id: group for group in self.groups}
        assigned_team_ids: set[object] = set()
        for group in self.groups:
            if len(group.team_ids) != 4:
                raise ValueError("each group must contain exactly four teams")
            assigned_team_ids.update(group.team_ids)
        if assigned_team_ids != {team.id for team in self.teams}:
            raise ValueError("group membership must contain every team exactly once")
        for team in self.teams:
            group = group_by_id.get(team.group_id)
            if group is None or team.id not in group.team_ids:
                raise ValueError("team group_id must match group membership")

    def _validate_venues_and_slots(self) -> None:
        time_zones = {venue.iana_time_zone for venue in self.venues}
        if len(time_zones) != 1:
            raise ValueError("both venues must use the same IANA timezone")
        venue_by_id = {venue.id: venue for venue in self.venues}
        for slot in self.slots:
            venue = venue_by_id.get(slot.venue_id)
            if venue is None:
                raise ValueError("every slot must reference a tournament venue")
            derived_date = slot.starts_at_utc.astimezone(ZoneInfo(venue.iana_time_zone)).date()
            if slot.local_date != derived_date:
                raise ValueError("slot local_date must match its venue IANA timezone")
