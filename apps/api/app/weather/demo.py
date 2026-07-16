from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import Field

from app.domain.common import DomainModel
from app.domain.venues import SlotAvailability, SlotSource, VenueSlot
from app.weather.normalize import NormalizedForecast
from app.weather.risk import (
    ConfirmedWeatherThresholds,
    FixtureWeatherRisk,
    WeatherThresholdCrossing,
    calculate_fixture_risk,
    evaluate_confirmed_thresholds,
)


class DemoWeatherScenario(DomainModel):
    scenario_id: str = Field(min_length=1, max_length=80)
    scenario_version: str = Field(pattern=r"^weather-demo/v\d+$")
    allocation_minutes: int = Field(gt=0)
    target_slot: VenueSlot
    thresholds: ConfirmedWeatherThresholds
    before: NormalizedForecast
    after: NormalizedForecast
    expected_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class DemoScenarioResult(DomainModel):
    before_risk: FixtureWeatherRisk
    after_risk: FixtureWeatherRisk
    before_crossings: tuple[WeatherThresholdCrossing, ...]
    after_crossings: tuple[WeatherThresholdCrossing, ...]
    affected_slot: VenueSlot
    deterministic_digest: str


def load_demo_scenario(path: Path) -> DemoWeatherScenario:
    return DemoWeatherScenario.model_validate_json(path.read_text(encoding="utf-8"))


def run_demo_scenario(scenario: DemoWeatherScenario) -> DemoScenarioResult:
    risk_arguments = {
        "fixture_starts_at_utc": scenario.target_slot.starts_at_utc,
        "allocation_minutes": scenario.allocation_minutes,
    }
    before_risk = calculate_fixture_risk(
        scenario.before.hours,
        **risk_arguments,
        forecast_fetched_at=scenario.before.fetched_at,
    )
    after_risk = calculate_fixture_risk(
        scenario.after.hours,
        **risk_arguments,
        forecast_fetched_at=scenario.after.fetched_at,
    )
    before_crossings = evaluate_confirmed_thresholds(
        scenario.before.hours,
        **risk_arguments,
        thresholds=scenario.thresholds,
    )
    after_crossings = evaluate_confirmed_thresholds(
        scenario.after.hours,
        **risk_arguments,
        thresholds=scenario.thresholds,
    )
    affected_slot = scenario.target_slot
    if after_crossings and not before_crossings:
        affected_slot = scenario.target_slot.model_copy(
            update={
                "availability": SlotAvailability.UNAVAILABLE,
                "source": SlotSource.DISRUPTION,
            }
        )
    digest_payload = {
        "scenario_id": scenario.scenario_id,
        "scenario_version": scenario.scenario_version,
        "before_risk": before_risk.model_dump(mode="json"),
        "after_risk": after_risk.model_dump(mode="json"),
        "before_crossings": [item.model_dump(mode="json") for item in before_crossings],
        "after_crossings": [item.model_dump(mode="json") for item in after_crossings],
        "affected_slot": affected_slot.model_dump(mode="json"),
    }
    canonical = json.dumps(digest_payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return DemoScenarioResult(
        before_risk=before_risk,
        after_risk=after_risk,
        before_crossings=before_crossings,
        after_crossings=after_crossings,
        affected_slot=affected_slot,
        deterministic_digest=digest,
    )
