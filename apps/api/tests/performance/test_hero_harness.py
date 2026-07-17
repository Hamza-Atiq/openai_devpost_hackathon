from __future__ import annotations

from performance.hero import run_repeated_hero


def test_deployed_like_hero_harness_runs_real_generation_validation_and_repair() -> None:
    report = run_repeated_hero(runs=1, workers=1)

    assert report["schema_version"] == "hero-reliability/v1"
    assert report["requested_runs"] == 1
    assert report["successful_runs"] == 1
    assert report["success_rate_percent"] == 100.0
    assert report["hard_valid_displayed_percent"] == 100.0
    assert report["cached_result_count"] == 0
    assert report["gpt_smoke_status"] == "not_run"
    assert report["runs"][0]["official_version_number"] == 2
    assert report["runs"][0]["meaningful_roles"] == [
        "tournament_director",
        "rules_constraint",
        "scheduling_strategy",
        "weather_intelligence",
        "fairness_logistics",
        "disruption_recovery",
    ]
    assert report["runs"][0]["changed_fixture_count"] >= 1
    assert report["runs"][0]["preserved_fixture_count"] >= 1
