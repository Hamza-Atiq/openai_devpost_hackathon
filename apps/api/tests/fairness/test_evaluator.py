from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.schedules import FixturePlacement
from app.fairness.evaluator import evaluate_schedule_metrics
from app.scheduling.pairings import generate_match_graph
from tests.domain.factories import valid_tournament


def _placements(tournament, matches):
    indexes = (*range(0, 12, 2), *range(1, 12, 2), 12, 13, 14)
    return tuple(
        FixturePlacement(
            match_id=match.id,
            slot_id=tournament.slots[index].id,
            venue_id=tournament.slots[index].venue_id,
            starts_at_utc=tournament.slots[index].starts_at_utc,
            ends_at_utc=tournament.slots[index].starts_at_utc
            + timedelta(minutes=tournament.allocation_minutes),
        )
        for match, index in zip(matches, indexes, strict=True)
    )


def test_schedule_metric_evaluator_is_deterministic_and_reports_unknown_weather() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    placements = _placements(tournament, matches)

    first = evaluate_schedule_metrics(tournament, matches, placements, slot_weather_risk={})
    second = evaluate_schedule_metrics(tournament, matches, placements, slot_weather_risk={})

    assert first == second
    assert first.weather_risk is None
    assert first.weather_coverage == 0
    assert first.missing_coverage_penalty > 0
    assert 0 <= first.group_rest_fairness <= 100
    assert 0 <= first.potential_knockout_rest <= 100
    assert 0 <= first.venue_balance <= 100
    assert 0 <= first.slot_balance <= 100
    assert first.preference_satisfaction == 100


def test_later_final_improves_final_path_without_changing_weather_claims() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    placements = list(_placements(tournament, matches))
    final = placements[-1]
    late_slot = tournament.slots[15]
    placements[-1] = final.model_copy(
        update={
            "slot_id": late_slot.id,
            "venue_id": late_slot.venue_id,
            "starts_at_utc": late_slot.starts_at_utc,
            "ends_at_utc": late_slot.starts_at_utc + timedelta(minutes=240),
        }
    )

    metrics = evaluate_schedule_metrics(
        tournament,
        matches,
        tuple(placements),
        slot_weather_risk={late_slot.id: None},
        evaluated_at=datetime(2026, 7, 16, tzinfo=UTC),
    )

    assert metrics.weather_risk is None
    assert metrics.weather_coverage == 0
