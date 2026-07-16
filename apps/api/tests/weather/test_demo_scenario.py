from __future__ import annotations

from pathlib import Path

from app.domain.venues import SlotAvailability, SlotSource
from app.weather.demo import load_demo_scenario, run_demo_scenario

SCENARIO_PATH = (
    Path(__file__).parents[2] / "app" / "weather" / "demo_scenarios" / "rain-threshold-v1.json"
)


def test_rain_scenario_is_identical_across_twenty_runs() -> None:
    scenario = load_demo_scenario(SCENARIO_PATH)
    results = tuple(run_demo_scenario(scenario) for _ in range(20))

    assert len({result.deterministic_digest for result in results}) == 1
    assert len({result.model_dump_json() for result in results}) == 1
    assert results[0].before_crossings == ()
    assert tuple(event.code for event in results[0].after_crossings) == (
        "precipitation_probability",
    )
    assert results[0].before_risk.risk < results[0].after_risk.risk
    assert results[0].affected_slot.id == scenario.target_slot.id
    assert results[0].affected_slot.availability is SlotAvailability.UNAVAILABLE
    assert results[0].affected_slot.source is SlotSource.DISRUPTION


def test_versioned_scenario_contains_provenance_and_expected_digest() -> None:
    scenario = load_demo_scenario(SCENARIO_PATH)
    result = run_demo_scenario(scenario)

    assert scenario.scenario_version == "weather-demo/v1"
    assert scenario.before.provider == "deterministic-demo"
    assert scenario.after.provider == "deterministic-demo"
    assert result.deterministic_digest == scenario.expected_digest
