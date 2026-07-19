from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal, Protocol

from app.domain.tournament import TournamentConfig
from app.weather.provider import OpenMeteoWeatherProvider, WeatherProviderUnavailableError
from app.weather.risk import calculate_fixture_risk


class WeatherServiceProtocol(Protocol):
    def refresh(
        self,
        tournament: TournamentConfig,
        *,
        mode: str,
        scenario_id: str | None = None,
    ) -> dict[str, object]: ...


class TournamentWeatherService:
    def __init__(self, provider: OpenMeteoWeatherProvider) -> None:
        self._provider = provider

    def refresh(
        self,
        tournament: TournamentConfig,
        *,
        mode: Literal["live", "deterministic"],
        scenario_id: str | None = None,
    ) -> dict[str, object]:
        if mode == "deterministic":
            return self._deterministic(tournament, scenario_id=scenario_id)
        return self._live(tournament)

    def _live(self, tournament: TournamentConfig) -> dict[str, object]:
        fetched_at = datetime.now(UTC)
        forecasts = {}
        for venue in tournament.venues:
            try:
                forecasts[venue.id] = self._provider.fetch(
                    latitude=venue.latitude,
                    longitude=venue.longitude,
                    iana_time_zone=venue.iana_time_zone,
                    start_date=tournament.start_date,
                    end_date=tournament.end_date,
                    fetched_at=fetched_at,
                )
            except WeatherProviderUnavailableError:
                continue

        details: dict[str, object] = {}
        risks: dict[str, float | None] = {}
        for slot in tournament.slots:
            forecast = forecasts.get(slot.venue_id)
            risk = (
                None
                if forecast is None
                else calculate_fixture_risk(
                    forecast.hours,
                    fixture_starts_at_utc=slot.starts_at_utc,
                    allocation_minutes=tournament.allocation_minutes,
                    forecast_fetched_at=forecast.fetched_at,
                )
            )
            risks[str(slot.id)] = None if risk is None else risk.risk
            details[str(slot.id)] = (
                {
                    "risk": None,
                    "covered": False,
                    "quality": "forecast_not_yet_available",
                    "components": {},
                    "forecast_fetched_at": None,
                }
                if risk is None
                else risk.model_dump(mode="json")
            )
        covered = sum(value is not None for value in risks.values())
        coverage = 0.0 if not risks else round(covered / len(risks) * 100, 1)
        issued = [forecast.issued_at or forecast.fetched_at for forecast in forecasts.values()]
        return {
            "mode": "live",
            "quality": "complete" if coverage == 100 else "partial" if coverage else "unavailable",
            "demo_mode_available": True,
            "scenario_id": None,
            "provider": "open-meteo",
            "fetched_at": fetched_at.isoformat(),
            "issued_at": max(issued).isoformat() if issued else None,
            "coverage": coverage,
            "slot_risks": risks,
            "slot_details": details,
            "attribution": "Weather data by Open-Meteo.com",
            "guidance": "Weather risk is planning guidance only.",
        }

    @staticmethod
    def _deterministic(
        tournament: TournamentConfig,
        *,
        scenario_id: str | None,
    ) -> dict[str, object]:
        risks: dict[str, float] = {}
        details: dict[str, object] = {}
        for slot in tournament.slots:
            digest = hashlib.sha256(f"weather-demo/v1:{slot.id}".encode()).digest()
            risk = float(10 + digest[0] % 76)
            risks[str(slot.id)] = risk
            details[str(slot.id)] = {
                "risk": risk,
                "covered": True,
                "quality": "complete",
                "components": {
                    "rain": risk,
                    "heat": float(digest[1] % 61),
                    "cold": 0.0,
                    "wind": float(digest[2] % 51),
                    "condition": float(digest[3] % 71),
                },
                "forecast_fetched_at": "2026-07-19T00:00:00Z",
                "provenance": "deterministic-weather/v1",
            }
        return {
            "mode": "deterministic",
            "quality": "complete",
            "demo_mode_available": True,
            "scenario_id": scenario_id or "rain-threshold-v1",
            "provider": "deterministic-demo",
            "fetched_at": "2026-07-19T00:00:00Z",
            "issued_at": "2026-07-19T00:00:00Z",
            "coverage": 100.0,
            "slot_risks": risks,
            "slot_details": details,
            "attribution": "Deterministic CrickOps weather scenario weather-demo/v1",
            "guidance": "Weather risk is planning guidance only.",
        }
