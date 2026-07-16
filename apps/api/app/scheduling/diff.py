from __future__ import annotations

from collections.abc import Sequence

from app.domain.common import UUID7
from app.domain.schedules import FixturePlacement, ScheduleDiff, ScheduleMetrics

_NUMERIC_METRICS = (
    "weather_risk",
    "weather_coverage",
    "missing_coverage_penalty",
    "group_rest_fairness",
    "potential_knockout_rest",
    "venue_balance",
    "slot_balance",
    "preference_satisfaction",
    "change_cost",
)


def _by_match(
    placements: Sequence[FixturePlacement],
) -> dict[UUID7, FixturePlacement]:
    result = {placement.match_id: placement for placement in placements}
    if len(result) != len(placements):
        raise ValueError("placements must reference a unique match")
    return result


def _metric_deltas(
    baseline: ScheduleMetrics,
    draft: ScheduleMetrics,
) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for name in _NUMERIC_METRICS:
        baseline_value = getattr(baseline, name)
        draft_value = getattr(draft, name)
        if baseline_value is not None and draft_value is not None:
            deltas[name] = float(draft_value - baseline_value)
    return deltas


def build_schedule_diff(
    *,
    baseline_version_id: UUID7,
    draft_id: UUID7,
    baseline: Sequence[FixturePlacement],
    draft: Sequence[FixturePlacement],
    baseline_metrics: ScheduleMetrics,
    draft_metrics: ScheduleMetrics,
) -> ScheduleDiff:
    """Compare a draft to an immutable official baseline.

    Metric deltas use ``draft - baseline`` so negative risk/cost values represent
    improvements while positive fairness and satisfaction values do the same.
    """
    baseline_by_match = _by_match(baseline)
    draft_by_match = _by_match(draft)

    unchanged = tuple(
        placement.match_id
        for placement in baseline
        if draft_by_match.get(placement.match_id) == placement
    )
    moved = tuple(
        placement.match_id
        for placement in baseline
        if placement.match_id in draft_by_match and draft_by_match[placement.match_id] != placement
    )
    removed = tuple(
        placement.match_id for placement in baseline if placement.match_id not in draft_by_match
    )
    added = tuple(
        placement.match_id for placement in draft if placement.match_id not in baseline_by_match
    )

    return ScheduleDiff(
        baseline_version_id=baseline_version_id,
        draft_id=draft_id,
        unchanged=unchanged,
        moved=moved,
        added=added,
        removed=removed,
        metric_deltas=_metric_deltas(baseline_metrics, draft_metrics),
    )
