from __future__ import annotations

from datetime import UTC, datetime

from app.domain.schedules import ScheduleMetrics, ScheduleProfile
from app.scheduling.comparison import compare_profile_options
from app.scheduling.pairings import generate_match_graph
from app.scheduling.profiles import generate_profile_options
from tests.domain.factories import valid_tournament

GENERATED_AT = datetime(2026, 7, 16, 10, tzinfo=UTC)


def _valid_unique_eligibility(tournament, matches):
    slot_indexes = (*range(0, 12, 2), *range(1, 12, 2), 12, 13, 14)
    return {
        match.id: frozenset((tournament.slots[slot_index].id,))
        for match, slot_index in zip(matches, slot_indexes, strict=True)
    }


def _metrics(_profile, _placements):
    return ScheduleMetrics(
        weather_risk=20,
        weather_coverage=100,
        group_rest_fairness=75,
        potential_knockout_rest=70,
        venue_balance=80,
        slot_balance=85,
        preference_satisfaction=90,
    )


def test_generates_three_independently_validated_profiles_and_reports_identical_results() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)

    batch = generate_profile_options(
        tournament,
        matches,
        _valid_unique_eligibility(tournament, matches),
        generated_at=GENERATED_AT,
        metric_evaluator=_metrics,
    )
    comparison = compare_profile_options(batch.options)

    assert batch.failures == ()
    assert [option.profile for option in batch.options] == [
        ScheduleProfile.BALANCED,
        ScheduleProfile.WEATHER_FIRST,
        ScheduleProfile.FAIRNESS_FIRST,
    ]
    assert all(option.validation_report.valid for option in batch.options)
    assert len({option.validation_report.placement_digest for option in batch.options}) == 1
    assert comparison.metric_version == "schedule-metrics/v1"
    assert comparison.identical_solution_groups == (
        (
            ScheduleProfile.BALANCED,
            ScheduleProfile.WEATHER_FIRST,
            ScheduleProfile.FAIRNESS_FIRST,
        ),
    )
    assert len({option.config_checksum for option in batch.options}) == 1


def test_custom_profile_runs_only_when_requested() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    eligible = _valid_unique_eligibility(tournament, matches)

    default_batch = generate_profile_options(
        tournament,
        matches,
        eligible,
        generated_at=GENERATED_AT,
        metric_evaluator=_metrics,
    )
    custom_batch = generate_profile_options(
        tournament,
        matches,
        eligible,
        generated_at=GENERATED_AT,
        metric_evaluator=_metrics,
        custom_priorities={"weather_coverage": 1, "rest": 1, "venue_balance": 2},
    )

    assert ScheduleProfile.CUSTOM not in {option.profile for option in default_batch.options}
    custom = next(
        option for option in custom_batch.options if option.profile is ScheduleProfile.CUSTOM
    )
    assert custom.weights == {
        "weather_coverage": 25,
        "rest": 25,
        "venue_balance": 50,
    }


def test_infeasible_runs_are_failures_and_never_displayed_as_options() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    no_slots = {match.id: frozenset() for match in matches}

    batch = generate_profile_options(
        tournament,
        matches,
        no_slots,
        generated_at=GENERATED_AT,
        metric_evaluator=_metrics,
    )

    assert batch.options == ()
    assert len(batch.failures) == 3
