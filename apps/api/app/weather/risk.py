from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from app.domain.common import DomainModel, UtcDateTime
from app.weather.normalize import NormalizedWeatherHour

_WEIGHTS = {
    "rain": Decimal("0.45"),
    "heat": Decimal("0.20"),
    "cold": Decimal("0.10"),
    "wind": Decimal("0.15"),
    "condition": Decimal("0.10"),
}


class WeatherRiskComponents(DomainModel):
    rain: float | None = Field(default=None, ge=0, le=100)
    heat: float | None = Field(default=None, ge=0, le=100)
    cold: float | None = Field(default=None, ge=0, le=100)
    wind: float | None = Field(default=None, ge=0, le=100)
    condition: float | None = Field(default=None, ge=0, le=100)


class FixtureWeatherRisk(DomainModel):
    risk: float | None = Field(default=None, ge=0, le=100)
    covered: bool
    quality: Literal["complete", "partial", "incomplete", "forecast_not_yet_available"]
    components: WeatherRiskComponents
    evaluated_from_utc: UtcDateTime
    evaluated_until_utc: UtcDateTime
    evaluated_hour_count: int = Field(ge=0)
    forecast_fetched_at: UtcDateTime | None = None
    provenance: str = "normalized-weather/v1"


class ScheduleWeatherSummary(DomainModel):
    weather_risk: float | None = Field(default=None, ge=0, le=100)
    weather_coverage: float = Field(ge=0, le=100)
    covered_fixture_count: int = Field(ge=0)
    uncovered_fixture_count: int = Field(ge=0)
    coverage_warning: bool


class WeatherThresholdCode(StrEnum):
    PRECIPITATION_PROBABILITY = "precipitation_probability"
    APPARENT_TEMPERATURE_HIGH = "apparent_temperature_high"
    APPARENT_TEMPERATURE_LOW = "apparent_temperature_low"
    WIND_SPEED = "wind_speed"
    WIND_GUST = "wind_gust"
    THUNDERSTORM = "thunderstorm"


class ConfirmedWeatherThresholds(DomainModel):
    confirmed: Literal[True]
    precipitation_probability_gte: float | None = Field(default=None, ge=0, le=100)
    apparent_temperature_gte: float | None = None
    apparent_temperature_lte: float | None = None
    wind_speed_gte: float | None = Field(default=None, ge=0)
    wind_gust_gte: float | None = Field(default=None, ge=0)
    thunderstorm_codes: tuple[int, ...] = ()

    @model_validator(mode="after")
    def require_a_threshold(self) -> ConfirmedWeatherThresholds:
        configured = (
            self.precipitation_probability_gte,
            self.apparent_temperature_gte,
            self.apparent_temperature_lte,
            self.wind_speed_gte,
            self.wind_gust_gte,
        )
        if all(value is None for value in configured) and not self.thunderstorm_codes:
            raise ValueError("at least one confirmed weather threshold is required")
        return self


class WeatherThresholdCrossing(DomainModel):
    code: WeatherThresholdCode
    observed_value: float
    threshold_value: float


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 100.0)


def _curve(value: float, safe: float, severe: float) -> float:
    return _clamp((value - safe) / (severe - safe) * 100)


def _inverse_curve(value: float, safe: float, severe: float) -> float:
    return _clamp((safe - value) / (safe - severe) * 100)


def _maximum(values: Sequence[float | int | None]) -> float | None:
    known = [float(value) for value in values if value is not None]
    return max(known) if known else None


def _condition_severity(code: int | None) -> float | None:
    if code is None:
        return None
    if 0 <= code <= 3:
        return 0
    if code in {45, 48}:
        return 20
    if 51 <= code <= 57:
        return 30
    if code in {61, 66, 80}:
        return 50
    if code in {63, 67, 81}:
        return 65
    if code in {65, 82}:
        return 80
    if 71 <= code <= 77 or code in {85, 86}:
        return 70
    if code == 95:
        return 90
    if code in {96, 99}:
        return 100
    return None


def _round_half_up(value: Decimal, places: str = "1") -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def calculate_fixture_risk(
    hours: Sequence[NormalizedWeatherHour],
    *,
    fixture_starts_at_utc: datetime,
    allocation_minutes: int,
    buffer_minutes: int = 30,
    forecast_fetched_at: datetime | None = None,
) -> FixtureWeatherRisk:
    window_start = fixture_starts_at_utc - timedelta(minutes=buffer_minutes)
    window_end = fixture_starts_at_utc + timedelta(minutes=allocation_minutes + buffer_minutes)
    relevant = tuple(hour for hour in hours if window_start <= hour.starts_at_utc <= window_end)
    if not relevant:
        return FixtureWeatherRisk(
            covered=False,
            quality="forecast_not_yet_available",
            components=WeatherRiskComponents(),
            evaluated_from_utc=window_start,
            evaluated_until_utc=window_end,
            evaluated_hour_count=0,
            forecast_fetched_at=forecast_fetched_at,
        )

    precipitation_probability = _maximum(tuple(hour.precipitation_probability for hour in relevant))
    precipitation_mm = _maximum(tuple(hour.precipitation_mm for hour in relevant))
    scaled_amount = None if precipitation_mm is None else _clamp(precipitation_mm / 5 * 100)
    rain = _maximum((precipitation_probability, scaled_amount))
    apparent_temperature = _maximum(
        tuple(
            hour.apparent_temperature_c
            if hour.apparent_temperature_c is not None
            else hour.temperature_c
            for hour in relevant
        )
    )
    minimum_temperature_values = tuple(
        hour.apparent_temperature_c
        if hour.apparent_temperature_c is not None
        else hour.temperature_c
        for hour in relevant
    )
    known_temperatures = [value for value in minimum_temperature_values if value is not None]
    minimum_temperature = min(known_temperatures) if known_temperatures else None
    sustained = _maximum(tuple(hour.wind_speed_kmh for hour in relevant))
    gust = _maximum(tuple(hour.wind_gust_kmh for hour in relevant))
    heat = None if apparent_temperature is None else _curve(apparent_temperature, 32, 45)
    cold = None if minimum_temperature is None else _inverse_curve(minimum_temperature, 12, 0)
    wind_parts = (
        None if sustained is None else _curve(sustained, 25, 60),
        None if gust is None else _curve(gust, 35, 75),
    )
    wind = _maximum(wind_parts)
    condition = _maximum(tuple(_condition_severity(hour.weather_code) for hour in relevant))
    components = WeatherRiskComponents(
        rain=rain,
        heat=heat,
        cold=cold,
        wind=wind,
        condition=condition,
    )
    covered = (
        precipitation_probability is not None
        and apparent_temperature is not None
        and wind is not None
    )
    known_components = {
        name: value
        for name, value in components.model_dump().items()
        if name != "schema_version" and value is not None
    }
    risk = None
    if covered:
        known_weight = sum(_WEIGHTS[name] for name in known_components)
        weighted_sum = sum(
            _WEIGHTS[name] * Decimal(str(value)) for name, value in known_components.items()
        )
        weighted_mean = weighted_sum / known_weight
        total = (
            Decimal("0.60") * Decimal(str(max(known_components.values())))
            + Decimal("0.40") * weighted_mean
        )
        risk = _round_half_up(total, "1")
    quality = "complete" if len(known_components) == 5 and covered else "partial"
    if not covered:
        quality = "incomplete"
    return FixtureWeatherRisk(
        risk=risk,
        covered=covered,
        quality=quality,
        components=components,
        evaluated_from_utc=window_start,
        evaluated_until_utc=window_end,
        evaluated_hour_count=len(relevant),
        forecast_fetched_at=forecast_fetched_at,
    )


def evaluate_confirmed_thresholds(
    hours: Sequence[NormalizedWeatherHour],
    *,
    fixture_starts_at_utc: datetime,
    allocation_minutes: int,
    thresholds: ConfirmedWeatherThresholds,
    buffer_minutes: int = 30,
) -> tuple[WeatherThresholdCrossing, ...]:
    window_start = fixture_starts_at_utc - timedelta(minutes=buffer_minutes)
    window_end = fixture_starts_at_utc + timedelta(minutes=allocation_minutes + buffer_minutes)
    relevant = tuple(hour for hour in hours if window_start <= hour.starts_at_utc <= window_end)
    crossings: list[WeatherThresholdCrossing] = []

    def add_high(
        code: WeatherThresholdCode,
        values: Sequence[float | int | None],
        threshold: float | None,
    ) -> None:
        observed = _maximum(values)
        if threshold is not None and observed is not None and observed >= threshold:
            crossings.append(
                WeatherThresholdCrossing(
                    code=code,
                    observed_value=observed,
                    threshold_value=threshold,
                )
            )

    add_high(
        WeatherThresholdCode.PRECIPITATION_PROBABILITY,
        tuple(hour.precipitation_probability for hour in relevant),
        thresholds.precipitation_probability_gte,
    )
    apparent_values = tuple(
        hour.apparent_temperature_c
        if hour.apparent_temperature_c is not None
        else hour.temperature_c
        for hour in relevant
    )
    add_high(
        WeatherThresholdCode.APPARENT_TEMPERATURE_HIGH,
        apparent_values,
        thresholds.apparent_temperature_gte,
    )
    known_apparent = [float(value) for value in apparent_values if value is not None]
    if thresholds.apparent_temperature_lte is not None and known_apparent:
        observed_low = min(known_apparent)
        if observed_low <= thresholds.apparent_temperature_lte:
            crossings.append(
                WeatherThresholdCrossing(
                    code=WeatherThresholdCode.APPARENT_TEMPERATURE_LOW,
                    observed_value=observed_low,
                    threshold_value=thresholds.apparent_temperature_lte,
                )
            )
    add_high(
        WeatherThresholdCode.WIND_SPEED,
        tuple(hour.wind_speed_kmh for hour in relevant),
        thresholds.wind_speed_gte,
    )
    add_high(
        WeatherThresholdCode.WIND_GUST,
        tuple(hour.wind_gust_kmh for hour in relevant),
        thresholds.wind_gust_gte,
    )
    observed_codes = {hour.weather_code for hour in relevant if hour.weather_code is not None}
    crossed_codes = sorted(observed_codes.intersection(thresholds.thunderstorm_codes))
    if crossed_codes:
        crossings.append(
            WeatherThresholdCrossing(
                code=WeatherThresholdCode.THUNDERSTORM,
                observed_value=crossed_codes[-1],
                threshold_value=crossed_codes[0],
            )
        )
    return tuple(crossings)


def summarize_schedule_weather(
    fixtures: Sequence[FixtureWeatherRisk],
) -> ScheduleWeatherSummary:
    known = [fixture.risk for fixture in fixtures if fixture.risk is not None]
    total = len(fixtures)
    covered = len(known)
    coverage = 0.0 if total == 0 else _round_half_up(Decimal(covered * 100) / total, "0.1")
    weather_risk = None
    if known:
        weather_risk = _round_half_up(
            sum(Decimal(str(value)) for value in known) / len(known), "0.1"
        )
    return ScheduleWeatherSummary(
        weather_risk=weather_risk,
        weather_coverage=coverage,
        covered_fixture_count=covered,
        uncovered_fixture_count=total - covered,
        coverage_warning=covered < total,
    )
