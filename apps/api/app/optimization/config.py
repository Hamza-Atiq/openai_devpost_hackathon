from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from app.domain.common import DomainModel

CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "optimization" / "v1.yaml"


class ObjectiveWeights(DomainModel):
    weather_coverage: int = Field(ge=0, le=100)
    rest: int = Field(ge=0, le=100)
    venue_balance: int = Field(ge=0, le=100)
    slot_balance: int = Field(ge=0, le=100)
    organizer_preferences: int = Field(ge=0, le=100)
    audience_timing: int = Field(ge=0, le=100)

    def values(self) -> tuple[int, ...]:
        return (
            self.weather_coverage,
            self.rest,
            self.venue_balance,
            self.slot_balance,
            self.organizer_preferences,
            self.audience_timing,
        )


class ProfileConfig(DomainModel):
    weights: ObjectiveWeights
    missing_coverage_penalty: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def weights_sum_to_one_hundred(self) -> ProfileConfig:
        if sum(self.weights.values()) != 100:
            raise ValueError("profile weights must sum to 100")
        return self


class WeatherComponentWeights(DomainModel):
    rain: int = Field(ge=0, le=100)
    heat: int = Field(ge=0, le=100)
    cold: int = Field(ge=0, le=100)
    wind: int = Field(ge=0, le=100)
    condition: int = Field(ge=0, le=100)


class HardThresholdSuggestions(DomainModel):
    precipitation_probability: int = Field(ge=0, le=100)
    apparent_temperature_max_celsius: int
    apparent_temperature_min_celsius: int
    sustained_wind_kmh: int = Field(ge=0)
    gust_kmh: int = Field(ge=0)
    thunderstorm_wmo_codes: tuple[int, ...]


class WeatherConfig(DomainModel):
    lead_minutes: int = Field(ge=0)
    lag_minutes: int = Field(ge=0)
    component_weights: WeatherComponentWeights
    risk_max_weight: int = Field(ge=0, le=100)
    risk_mean_weight: int = Field(ge=0, le=100)
    coverage_required: tuple[str, ...]
    rain_mm_full_risk: int = Field(gt=0)
    heat_curve_celsius: tuple[tuple[int, int], ...]
    cold_curve_celsius: tuple[tuple[int, int], ...]
    sustained_wind_curve_kmh: tuple[tuple[int, int], ...]
    gust_curve_kmh: tuple[tuple[int, int], ...]
    condition_scores: dict[str, int]
    hard_threshold_suggestions: HardThresholdSuggestions

    @model_validator(mode="after")
    def validate_weather_weights(self) -> WeatherConfig:
        if sum(self.component_weights.model_dump(exclude={"schema_version"}).values()) != 100:
            raise ValueError("weather component weights must sum to 100")
        if self.risk_max_weight + self.risk_mean_weight != 100:
            raise ValueError("weather risk blend weights must sum to 100")
        return self


class RoundingConfig(DomainModel):
    display_decimal_places: Literal[1]
    solver_scale: Literal[10]
    solver_max: Literal[1000]


class CustomConfig(DomainModel):
    minimum: Literal[0]
    maximum: Literal[100]
    all_zero_allowed: Literal[False]
    default_missing_coverage_penalty: int = Field(ge=0, le=100)


class SlotCategories(DomainModel):
    morning: tuple[str, str]
    day: tuple[str, str]
    evening: tuple[str, str]
    off_hours: tuple[str, str]


class AudienceConfig(DomainModel):
    prime_slot_satisfaction: int = Field(ge=0, le=100)
    weekend_satisfaction: int = Field(ge=0, le=100)
    standard_satisfaction: int = Field(ge=0, le=100)
    off_hours_satisfaction: int = Field(ge=0, le=100)
    off_hours_penalty: int = Field(ge=0, le=100)


class RestConfig(DomainModel):
    full_margin_minutes: int = Field(gt=0)
    mean_weight: int = Field(ge=0, le=100)
    equity_weight: int = Field(ge=0, le=100)


class PreferenceConfig(DomainModel):
    exact_satisfaction: Literal[100]
    partial_satisfaction: Literal[50]
    violation_satisfaction: Literal[0]
    priority_minimum: Literal[1]
    priority_maximum: Literal[100]


class OptimizationConfig(DomainModel):
    version: Literal["optimization-config/v1"]
    rounding: RoundingConfig
    weather: WeatherConfig
    profiles: dict[str, ProfileConfig]
    custom: CustomConfig
    slot_categories: SlotCategories
    audience: AudienceConfig
    rest: RestConfig
    preference: PreferenceConfig

    @model_validator(mode="after")
    def validate_profiles_and_rest(self) -> OptimizationConfig:
        if set(self.profiles) != {"balanced", "weather-first", "fairness-first"}:
            raise ValueError("configuration requires the three Version 1 profiles")
        if self.rest.mean_weight + self.rest.equity_weight != 100:
            raise ValueError("rest weights must sum to 100")
        return self


def load_optimization_config(path: Path = CONFIG_PATH) -> OptimizationConfig:
    return OptimizationConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))


def config_checksum(path: Path = CONFIG_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display_round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def solver_coefficient(value: Decimal) -> int:
    return int((value * 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def normalize_custom_priorities(values: dict[str, int]) -> dict[str, Decimal]:
    if any(value < 0 or value > 100 for value in values.values()):
        raise ValueError("custom priorities must be between 0 and 100")
    total = sum(values.values())
    if total == 0:
        raise ValueError("all-zero custom priorities are not allowed")
    return {name: Decimal(value) * Decimal(100) / Decimal(total) for name, value in values.items()}
