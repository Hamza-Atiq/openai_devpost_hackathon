from __future__ import annotations

from decimal import Decimal

from app.fairness.metrics import (
    PreferenceOutcome,
    group_rest_fairness,
    knockout_rest_metrics,
    preference_satisfaction,
    schedule_weather_metrics,
    slot_balance,
    venue_balance,
)


def test_weather_risk_and_coverage_remain_separate_with_missing_penalty() -> None:
    metrics = schedule_weather_metrics(
        fixture_risks=(Decimal("20"),) * 10 + (None,) * 5,
        missing_coverage_penalty=Decimal("55"),
    )

    assert metrics.weather_risk == Decimal("20.0")
    assert metrics.weather_coverage == Decimal("66.7")
    assert metrics.objective_penalty == Decimal("31.7")
    assert metrics.missing_fixture_count == 5


def test_group_rest_uses_mean_quality_and_equity() -> None:
    metrics = group_rest_fairness(
        {
            "team-a": 0,
            "team-b": 1440,
            "team-c": 720,
            "team-d": 720,
        }
    )

    assert metrics.per_team_quality == {
        "team-a": Decimal("0.0"),
        "team-b": Decimal("100.0"),
        "team-c": Decimal("50.0"),
        "team-d": Decimal("50.0"),
    }
    assert metrics.rest_equity == Decimal("0.0")
    assert metrics.score == Decimal("25.0")


def test_knockout_rest_reports_exclusive_role_worst_cases_and_final_path() -> None:
    metrics = knockout_rest_metrics(
        {
            "team-a": (1200, 900),
            "team-b": (1500, 1800),
            "team-c": (600, 720),
        },
        semifinal_to_final_minutes=(1000, 800),
    )

    assert metrics.per_team_minimum_minutes == {
        "team-a": 900,
        "team-b": 1500,
        "team-c": 600,
    }
    assert metrics.minimum_minutes == 600
    assert metrics.median_minutes == 900
    assert metrics.final_minimum_minutes == 800
    assert metrics.score == Decimal("41.7")


def test_venue_and_slot_balance_match_golden_vectors() -> None:
    assert venue_balance({"a": (2, 1), "b": (1, 2), "c": (3, 0)}) == Decimal("66.7")
    assert slot_balance(
        team_category_counts={
            "a": {"morning": 2, "day": 1, "evening": 0},
            "b": {"morning": 0, "day": 1, "evening": 2},
        },
        tournament_category_counts={"morning": 2, "day": 2, "evening": 2},
    ) == Decimal("66.7")


def test_preference_satisfaction_is_priority_weighted() -> None:
    score = preference_satisfaction(
        (
            PreferenceOutcome(preference_id="prime", priority=100, satisfaction=100),
            PreferenceOutcome(preference_id="venue", priority=50, satisfaction=50),
            PreferenceOutcome(preference_id="rivalry", priority=50, satisfaction=0),
        )
    )

    assert score == Decimal("62.5")
