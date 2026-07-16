from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from pydantic import Field

from app.domain.common import DomainModel
from app.optimization.config import display_round

ZERO = Decimal(0)
HUNDRED = Decimal(100)


def _clamp(value: Decimal, minimum: Decimal = ZERO, maximum: Decimal = HUNDRED) -> Decimal:
    return min(max(value, minimum), maximum)


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, ZERO) / Decimal(len(values))


class WeatherScheduleMetrics(DomainModel):
    weather_risk: Decimal | None
    weather_coverage: Decimal
    objective_penalty: Decimal
    missing_fixture_count: int = Field(ge=0, le=15)


class GroupRestMetrics(DomainModel):
    per_team_quality: Mapping[str, Decimal]
    rest_equity: Decimal
    score: Decimal


class KnockoutRestMetrics(DomainModel):
    per_team_minimum_minutes: Mapping[str, int]
    minimum_minutes: int
    median_minutes: Decimal
    final_minimum_minutes: int
    score: Decimal


class PreferenceOutcome(DomainModel):
    preference_id: str
    priority: int = Field(ge=1, le=100)
    satisfaction: int = Field(ge=0, le=100)


def schedule_weather_metrics(
    fixture_risks: Sequence[Decimal | None],
    missing_coverage_penalty: Decimal,
) -> WeatherScheduleMetrics:
    if len(fixture_risks) != 15:
        raise ValueError("Version 1 weather metrics require exactly 15 fixtures")
    known = tuple(value for value in fixture_risks if value is not None)
    missing_count = 15 - len(known)
    risk = display_round(_mean(known)) if known else None
    coverage = display_round(Decimal(len(known)) / Decimal(15) * HUNDRED)
    objective_values = (*known, *((missing_coverage_penalty,) * missing_count))
    objective_penalty = display_round(_mean(objective_values))
    return WeatherScheduleMetrics(
        weather_risk=risk,
        weather_coverage=coverage,
        objective_penalty=objective_penalty,
        missing_fixture_count=missing_count,
    )


def group_rest_fairness(rest_margins_minutes: Mapping[str, int]) -> GroupRestMetrics:
    if not rest_margins_minutes:
        raise ValueError("group rest metrics require at least one team")
    raw_quality = {
        team_id: _clamp(Decimal(max(margin, 0)) / Decimal(1440) * HUNDRED)
        for team_id, margin in rest_margins_minutes.items()
    }
    values = tuple(raw_quality.values())
    equity = HUNDRED - (max(values) - min(values))
    score = Decimal("0.5") * _mean(values) + Decimal("0.5") * equity
    return GroupRestMetrics(
        per_team_quality={team_id: display_round(value) for team_id, value in raw_quality.items()},
        rest_equity=display_round(equity),
        score=display_round(score),
    )


def knockout_rest_metrics(
    role_path_minutes_by_team: Mapping[str, Sequence[int]],
    semifinal_to_final_minutes: Sequence[int],
) -> KnockoutRestMetrics:
    if not role_path_minutes_by_team or len(semifinal_to_final_minutes) != 2:
        raise ValueError("knockout rest requires team role paths and two final paths")
    per_team = {
        team_id: min(path_minutes)
        for team_id, path_minutes in role_path_minutes_by_team.items()
        if path_minutes
    }
    if len(per_team) != len(role_path_minutes_by_team):
        raise ValueError("every team must have at least one qualification path")
    ordered = sorted(per_team.values())
    middle = len(ordered) // 2
    median = (
        Decimal(ordered[middle])
        if len(ordered) % 2
        else Decimal(ordered[middle - 1] + ordered[middle]) / Decimal(2)
    )
    minimum = min(ordered)
    score = _clamp(Decimal(max(minimum, 0)) / Decimal(1440) * HUNDRED)
    return KnockoutRestMetrics(
        per_team_minimum_minutes=per_team,
        minimum_minutes=minimum,
        median_minutes=median,
        final_minimum_minutes=min(semifinal_to_final_minutes),
        score=display_round(score),
    )


def venue_balance(team_venue_counts: Mapping[str, tuple[int, int]]) -> Decimal:
    if not team_venue_counts:
        raise ValueError("venue balance requires team appearance counts")
    imbalances = tuple(
        _clamp((Decimal(abs(first - second)) - Decimal(1)) / Decimal(2) * HUNDRED)
        for first, second in team_venue_counts.values()
    )
    return display_round(HUNDRED - _mean(imbalances))


def slot_balance(
    team_category_counts: Mapping[str, Mapping[str, int]],
    tournament_category_counts: Mapping[str, int],
) -> Decimal:
    tournament_total = sum(tournament_category_counts.values())
    if not team_category_counts or tournament_total == 0:
        raise ValueError("slot balance requires team and tournament category counts")
    categories = tuple(tournament_category_counts)
    tournament_proportions = {
        category: Decimal(tournament_category_counts[category]) / Decimal(tournament_total)
        for category in categories
    }
    distances: list[Decimal] = []
    for counts in team_category_counts.values():
        team_total = sum(counts.values())
        if team_total == 0:
            raise ValueError("every team must have categorized appearances")
        distance = sum(
            (
                abs(
                    Decimal(counts.get(category, 0)) / Decimal(team_total)
                    - tournament_proportions[category]
                )
                for category in categories
            ),
            ZERO,
        ) / Decimal(2)
        distances.append(distance)
    return display_round(HUNDRED - _mean(distances) * HUNDRED)


def preference_satisfaction(outcomes: Sequence[PreferenceOutcome]) -> Decimal:
    if not outcomes:
        return HUNDRED
    possible = sum((Decimal(outcome.priority) for outcome in outcomes), ZERO)
    achieved = sum(
        (
            Decimal(outcome.priority) * Decimal(outcome.satisfaction) / HUNDRED
            for outcome in outcomes
        ),
        ZERO,
    )
    return display_round(achieved / possible * HUNDRED)
