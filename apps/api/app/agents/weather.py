from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Literal

from agents import Agent
from pydantic import Field

from app.agents.instructions import build_agent_instructions
from app.agents.schemas import AgentMode, AgentRole, EvidenceRef
from app.agents.specialist_tools import require_allowed_tools
from app.domain.common import DomainModel, UtcDateTime

GUIDANCE_DISCLAIMER = (
    "Forecast-based weather risk is planning guidance only, not an official safety "
    "decision or a guarantee of forecast precision or washout prevention."
)


class VenueWeatherEvidence(DomainModel):
    venue_id: str = Field(min_length=1, max_length=240)
    provider_state: Literal["fresh", "stale", "unavailable"]
    fetched_at: UtcDateTime


class FixtureRiskEvidence(DomainModel):
    risk: float | None = Field(default=None, ge=0, le=100)
    covered: bool
    quality: Literal["complete", "partial", "incomplete", "forecast_not_yet_available"]


class WeatherAnalysisInput(DomainModel):
    venue_snapshots: tuple[VenueWeatherEvidence, ...]
    fixture_risks: Mapping[str, FixtureRiskEvidence]
    weather_coverage: float = Field(ge=0, le=100)
    threshold_events: tuple[str, ...] = ()
    mode: AgentMode


class WeatherAnalysisOutput(DomainModel):
    high_risk_fixtures: tuple[str, ...] = ()
    uncertainty_notes: tuple[str, ...] = ()
    threshold_events: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)
    guidance_disclaimer: Literal[
        "Forecast-based weather risk is planning guidance only, not an official safety "
        "decision or a guarantee of forecast precision or washout prevention."
    ] = GUIDANCE_DISCLAIMER


_UNSUPPORTED_CLAIM = re.compile(
    r"\b(radar|nowcast|guarantee(?:s|d)?|will be washed out|cannot be washed out)\b",
    re.IGNORECASE,
)


def validate_weather_analysis(
    turn_input: WeatherAnalysisInput,
    output: WeatherAnalysisOutput,
) -> WeatherAnalysisOutput:
    unknown_fixtures = set(output.high_risk_fixtures).difference(turn_input.fixture_risks)
    if unknown_fixtures:
        raise ValueError("weather output referenced a fixture without deterministic evidence")
    if any(turn_input.fixture_risks[item].risk is None for item in output.high_risk_fixtures):
        raise ValueError("unknown fixture risk cannot be described as high risk")
    if not set(output.threshold_events).issubset(turn_input.threshold_events):
        raise ValueError("weather output invented a threshold event")
    if turn_input.weather_coverage < 100 and not output.uncertainty_notes:
        raise ValueError("incomplete weather coverage requires an uncertainty note")
    if any(_UNSUPPORTED_CLAIM.search(text) for text in output.alternatives):
        raise ValueError("weather output contains an unsupported weather claim")
    return output


_ALLOWED_TOOLS = frozenset(
    {"fetch_weather", "refresh_weather", "calculate_weather_risk", "compare_fixture_risk"}
)


def create_weather_agent(
    *,
    model: str = "gpt-5.6",
    tools: Sequence[object] = (),
) -> Agent:
    return Agent(
        name="Weather Intelligence Specialist",
        instructions=build_agent_instructions(AgentRole.WEATHER_INTELLIGENCE),
        model=model,
        output_type=WeatherAnalysisOutput,
        tools=require_allowed_tools(tools, _ALLOWED_TOOLS),
    )
