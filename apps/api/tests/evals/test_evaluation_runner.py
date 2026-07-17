from __future__ import annotations

from evals.run import run_evaluations


def test_versioned_corpus_passes_all_cases_and_safety_metrics() -> None:
    report = run_evaluations()

    assert report["schema_version"] == "eval-report/v1"
    assert report["case_count"] == 9
    assert report["passed_count"] == 9
    assert report["failed_cases"] == []
    assert report["metrics"]["hard_valid_displayed_percent"] == 100.0
    assert report["metrics"]["seeded_infeasible_blocked_percent"] == 100.0
    assert report["metrics"]["displayed_schedule_and_repair_count"] == 4
    assert report["metrics"]["hard_valid_displayed_count"] == 4
    assert report["metrics"]["seeded_infeasible_count"] == 2
    assert report["metrics"]["seeded_infeasible_blocked_count"] == 2
    assert set(report["covered_categories"]) == {
        "feasible",
        "infeasible",
        "format",
        "overlap",
        "knockout",
        "weather",
        "repair",
        "provider",
        "feedback",
    }
    assert set(report["covered_requirements"]) == {
        *(f"AC-{index:03d}" for index in range(1, 28)),
        *(f"METRIC-{index:03d}" for index in range(1, 9)),
    }
