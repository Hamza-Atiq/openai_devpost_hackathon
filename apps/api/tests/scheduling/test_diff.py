from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.domain.schedules import FixturePlacement, ScheduleMetrics
from app.scheduling.diff import build_schedule_diff
from tests.domain.factories import uuid7

START = datetime(2026, 7, 16, 9, tzinfo=UTC)


def _placement(match_seed: int, slot_seed: int, venue_seed: int, hour: int) -> FixturePlacement:
    starts_at = START + timedelta(hours=hour)
    return FixturePlacement(
        match_id=uuid7(match_seed),
        slot_id=uuid7(slot_seed),
        venue_id=uuid7(venue_seed),
        starts_at_utc=starts_at,
        ends_at_utc=starts_at + timedelta(hours=4),
    )


def test_diff_classifies_placements_and_calculates_draft_minus_baseline_metrics() -> None:
    unchanged = _placement(1, 101, 201, 0)
    moved_before = _placement(2, 102, 201, 4)
    removed = _placement(3, 103, 202, 8)
    moved_after = _placement(2, 104, 202, 12)
    added = _placement(4, 105, 201, 16)
    baseline = (unchanged, moved_before, removed)
    draft = (unchanged, moved_after, added)

    result = build_schedule_diff(
        baseline_version_id=uuid7(501),
        draft_id=uuid7(502),
        baseline=baseline,
        draft=draft,
        baseline_metrics=ScheduleMetrics(
            weather_risk=40,
            weather_coverage=80,
            group_rest_fairness=70,
            change_cost=0,
        ),
        draft_metrics=ScheduleMetrics(
            weather_risk=30,
            weather_coverage=100,
            group_rest_fairness=75,
            change_cost=1,
        ),
    )

    assert result.unchanged == (unchanged.match_id,)
    assert result.moved == (moved_before.match_id,)
    assert result.added == (added.match_id,)
    assert result.removed == (removed.match_id,)
    assert result.metric_deltas["weather_risk"] == -10
    assert result.metric_deltas["weather_coverage"] == 20
    assert result.metric_deltas["group_rest_fairness"] == 5
    assert result.metric_deltas["change_cost"] == 1


def test_diff_rejects_duplicate_match_placements() -> None:
    placement = _placement(1, 101, 201, 0)

    with pytest.raises(ValueError, match="unique match"):
        build_schedule_diff(
            baseline_version_id=uuid7(501),
            draft_id=uuid7(502),
            baseline=(placement, placement),
            draft=(placement,),
            baseline_metrics=ScheduleMetrics(),
            draft_metrics=ScheduleMetrics(),
        )


def test_metric_delta_is_omitted_when_either_weather_value_is_unknown() -> None:
    placement = _placement(1, 101, 201, 0)

    result = build_schedule_diff(
        baseline_version_id=uuid7(501),
        draft_id=uuid7(502),
        baseline=(placement,),
        draft=(placement,),
        baseline_metrics=ScheduleMetrics(weather_risk=None),
        draft_metrics=ScheduleMetrics(weather_risk=25),
    )

    assert "weather_risk" not in result.metric_deltas
