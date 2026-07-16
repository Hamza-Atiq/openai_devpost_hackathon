from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domain.matches import MatchDefinition, MatchStage
from app.domain.schedules import FixturePlacement, ScheduleMetrics
from app.domain.tournament import TournamentConfig
from app.fairness.metrics import (
    group_rest_fairness,
    knockout_rest_metrics,
    preference_satisfaction,
    schedule_weather_metrics,
    slot_balance,
    venue_balance,
)
from app.optimization.config import load_optimization_config


def _slot_category(hour: int) -> str:
    if 6 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 16:
        return "day"
    if 17 <= hour <= 22:
        return "evening"
    return "off_hours"


def _known_group_teams(match: MatchDefinition) -> tuple[str, str]:
    if match.stage is not MatchStage.GROUP:
        raise ValueError("known team lookup applies only to group matches")
    return match.participant_a, match.participant_b


def evaluate_schedule_metrics(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
    placements: Sequence[FixturePlacement],
    *,
    slot_weather_risk: Mapping[UUID, Decimal | float | None],
    evaluated_at: datetime | None = None,
    missing_coverage_penalty: Decimal | None = None,
) -> ScheduleMetrics:
    """Calculate comparable metrics from one validated placement set."""
    del evaluated_at
    if len(matches) != 15 or len(placements) != 15:
        raise ValueError("Version 1 schedule evaluation requires 15 matches and placements")
    placement_by_match = {placement.match_id: placement for placement in placements}
    if set(placement_by_match) != {match.id for match in matches}:
        raise ValueError("placements must cover the fixed match graph exactly")

    config = load_optimization_config()
    missing_penalty = missing_coverage_penalty or Decimal(
        config.profiles["balanced"].missing_coverage_penalty
    )
    risks = tuple(
        None
        if slot_weather_risk.get(placement.slot_id) is None
        else Decimal(str(slot_weather_risk[placement.slot_id]))
        for placement in placements
    )
    weather = schedule_weather_metrics(risks, missing_penalty)

    group_matches = tuple(match for match in matches if match.stage is MatchStage.GROUP)
    semifinals = tuple(match for match in matches if match.stage is MatchStage.SEMIFINAL)
    final = next(match for match in matches if match.stage is MatchStage.FINAL)
    team_appearances: dict[str, list[FixturePlacement]] = defaultdict(list)
    venue_counts: dict[str, Counter[UUID]] = defaultdict(Counter)
    category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    tournament_categories: Counter[str] = Counter()
    venue_by_id = {venue.id: venue for venue in tournament.venues}

    for match in group_matches:
        placement = placement_by_match[match.id]
        venue = venue_by_id[placement.venue_id]
        local_hour = placement.starts_at_utc.astimezone(ZoneInfo(venue.iana_time_zone)).hour
        category = _slot_category(local_hour)
        tournament_categories[category] += 1
        for team_id in _known_group_teams(match):
            team_appearances[team_id].append(placement)
            venue_counts[team_id][placement.venue_id] += 1
            category_counts[team_id][category] += 1

    rest_margins: dict[str, int] = {}
    for team_id, appearances in team_appearances.items():
        ordered = sorted(appearances, key=lambda item: item.starts_at_utc)
        rest_margins[team_id] = min(
            int((later.starts_at_utc - earlier.ends_at_utc).total_seconds() // 60)
            for earlier, later in zip(ordered[:-1], ordered[1:], strict=True)
        )
    group_rest = group_rest_fairness(rest_margins)

    semifinal_placements = tuple(placement_by_match[match.id] for match in semifinals)
    role_path_minutes: dict[str, tuple[int, ...]] = {}
    for team_id, appearances in team_appearances.items():
        last_group_end = max(appearances, key=lambda item: item.ends_at_utc).ends_at_utc
        role_path_minutes[team_id] = tuple(
            int((semifinal.starts_at_utc - last_group_end).total_seconds() // 60)
            for semifinal in semifinal_placements
        )
    final_placement = placement_by_match[final.id]
    semifinal_to_final = tuple(
        int((final_placement.starts_at_utc - semifinal.ends_at_utc).total_seconds() // 60)
        for semifinal in semifinal_placements
    )
    knockout_rest = knockout_rest_metrics(role_path_minutes, semifinal_to_final)

    venue_ids = tuple(venue.id for venue in tournament.venues)
    venue_score = venue_balance(
        {
            team_id: (counts[venue_ids[0]], counts[venue_ids[1]])
            for team_id, counts in venue_counts.items()
        }
    )
    all_categories = ("morning", "day", "evening", "off_hours")
    slot_score = slot_balance(
        {
            team_id: {category: counts[category] for category in all_categories}
            for team_id, counts in category_counts.items()
        },
        {category: tournament_categories[category] for category in all_categories},
    )

    soft_violations = ()
    if weather.missing_fixture_count:
        soft_violations = (
            f"Weather coverage unavailable for {weather.missing_fixture_count} fixtures",
        )
    return ScheduleMetrics(
        weather_risk=None if weather.weather_risk is None else float(weather.weather_risk),
        weather_coverage=float(weather.weather_coverage),
        missing_coverage_penalty=float(weather.objective_penalty),
        group_rest_fairness=float(group_rest.score),
        potential_knockout_rest=float(knockout_rest.score),
        venue_balance=float(venue_score),
        slot_balance=float(slot_score),
        preference_satisfaction=float(preference_satisfaction(())),
        soft_violations=soft_violations,
    )
