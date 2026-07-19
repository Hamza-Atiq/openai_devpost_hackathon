from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from app.agents.director import SpecialistRequest
from app.agents.fairness import FairnessAuditInput
from app.agents.recovery import (
    DisruptionKind,
    RecoveryInput,
    RecoveryOptionEvidence,
)
from app.agents.schemas import AgentMode, AgentRole
from app.agents.specialist_evidence import build_specialist_request
from app.agents.specialist_runtime import SpecialistRunRequest, SpecialistRuntimeResult
from app.agents.weather import (
    FixtureRiskEvidence,
    VenueWeatherEvidence,
    WeatherAnalysisInput,
)
from app.api.workspace import GuestWorkspace
from app.domain.schedules import ScheduleDiff


class SpecialistRunnerProtocol(Protocol):
    async def run(self, request: SpecialistRunRequest) -> SpecialistRuntimeResult: ...


def _numeric_metrics(values: Mapping[str, object]) -> dict[str, float]:
    return {
        str(name): float(value)
        for name, value in values.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }


class WorkflowAgentOrchestrator:
    def __init__(self, runtime: SpecialistRunnerProtocol) -> None:
        self._runtime = runtime

    def _weather_request(
        self,
        workspace: GuestWorkspace,
        *,
        draft_id: str,
        reason: str,
    ) -> SpecialistRunRequest:
        tournament = workspace.tournament
        draft = workspace.drafts[draft_id]
        if tournament is None:
            raise ValueError("weather specialist requires a tournament")
        slot_risks = workspace.weather.get("slot_risks", {})
        slot_details = workspace.weather.get("slot_details", {})
        if not isinstance(slot_risks, dict):
            slot_risks = {}
        if not isinstance(slot_details, dict):
            slot_details = {}
        fixture_risks: dict[str, FixtureRiskEvidence] = {}
        for placement in draft.placements:
            slot_id = str(placement.slot_id)
            risk = slot_risks.get(slot_id)
            detail = slot_details.get(slot_id, {})
            detail = detail if isinstance(detail, dict) else {}
            covered = isinstance(risk, int | float) and not isinstance(risk, bool)
            quality = str(detail.get("quality", "complete" if covered else "incomplete"))
            if quality not in {
                "complete",
                "partial",
                "incomplete",
                "forecast_not_yet_available",
            }:
                quality = "incomplete"
            fixture_risks[str(placement.match_id)] = FixtureRiskEvidence(
                risk=float(risk) if covered else None,
                covered=covered,
                quality=quality,
            )
        fetched_at = workspace.weather.get("fetched_at") or datetime.now(UTC)
        weather_quality = str(workspace.weather.get("quality", "unavailable"))
        provider_state = "fresh" if weather_quality in {"complete", "partial"} else "unavailable"
        snapshots = tuple(
            VenueWeatherEvidence(
                venue_id=str(venue.id),
                provider_state=provider_state,
                fetched_at=fetched_at,
            )
            for venue in tournament.venues
        )
        covered_count = sum(item.covered for item in fixture_risks.values())
        coverage = (
            round(covered_count / len(fixture_risks) * 100, 1) if fixture_risks else 0.0
        )
        return SpecialistRunRequest(
            role=AgentRole.WEATHER_INTELLIGENCE,
            payload=WeatherAnalysisInput(
                venue_snapshots=snapshots,
                fixture_risks=fixture_risks,
                weather_coverage=coverage,
                threshold_events=tuple(workspace.weather.get("threshold_events", ())),
                mode=AgentMode.GPT_5_6,
            ),
            invocation_reason=reason,
            tournament_revision=tournament.revision,
            consumed_fields=("fixture_risks", "weather_coverage"),
            tool_name="compare_fixture_risk",
            deterministic_authority=True,
        )

    def _fairness_request(
        self,
        workspace: GuestWorkspace,
        *,
        draft_id: str,
        reason: str,
    ) -> SpecialistRunRequest:
        tournament = workspace.tournament
        draft = workspace.drafts[draft_id]
        if tournament is None:
            raise ValueError("fairness specialist requires a tournament")
        return SpecialistRunRequest(
            role=AgentRole.FAIRNESS_LOGISTICS,
            payload=FairnessAuditInput(
                schedule_id=draft_id,
                validation_valid=draft.validation_report.valid,
                metric_version="schedule-metrics/v1",
                metrics=_numeric_metrics(
                    draft.metrics.model_dump(mode="json", exclude={"schema_version"})
                ),
                team_breakdown={},
            ),
            invocation_reason=reason,
            tournament_revision=tournament.revision,
            consumed_fields=("validation_valid", "metrics"),
            tool_name="read_validated_metrics",
            deterministic_authority=True,
        )

    async def after_generation(
        self,
        *,
        workspace: GuestWorkspace,
        run: Mapping[str, object],
    ) -> tuple[Mapping[str, object], ...]:
        options = list(run.get("options", ()))
        if not options:
            return ()
        first_draft_id = str(options[0]["draft_id"])
        strategy_request = build_specialist_request(
            workspace,
            SpecialistRequest(
                role=AgentRole.SCHEDULING_STRATEGY,
                reason="Compare solver-generated profiles using validated metrics",
                required_evidence=("validated_schedule_comparison",),
            ),
            "Compare the generated scheduling profiles using their validated metrics.",
        )
        if strategy_request is None:
            raise ValueError("strategy evidence could not be prepared")
        strategy, weather = await asyncio.gather(
            self._runtime.run(strategy_request),
            self._runtime.run(
                self._weather_request(
                    workspace,
                    draft_id=first_draft_id,
                    reason="Explain validated schedule weather risk and coverage",
                )
            ),
        )
        fairness = await self._runtime.run(
            self._fairness_request(
                workspace,
                draft_id=first_draft_id,
                reason="Independently audit validated fairness and logistics metrics",
            )
        )
        return tuple(
            result.model_dump(mode="json") for result in (strategy, weather, fairness)
        )

    async def after_repair(
        self,
        *,
        workspace: GuestWorkspace,
        draft_id: str,
        disruption: Mapping[str, object],
        diff: Mapping[str, object],
    ) -> tuple[Mapping[str, object], ...]:
        tournament = workspace.tournament
        if tournament is None or not workspace.official_versions:
            return ()
        official = workspace.official_versions[-1]
        baseline = workspace.drafts[str(official["approved_draft_id"])]
        unavailable = {str(value) for value in disruption["unavailable_slot_ids"]}
        affected = tuple(
            placement.match_id
            for placement in baseline.placements
            if str(placement.slot_id) in unavailable
        )
        recovery_request = SpecialistRunRequest(
            role=AgentRole.DISRUPTION_RECOVERY,
            payload=RecoveryInput(
                official_version_id=official["version_id"],
                disruption_kind=(
                    DisruptionKind.VENUE_UNAVAILABLE
                    if disruption["type"] == "venue_unavailability"
                    else DisruptionKind.RAIN
                ),
                unavailable_slot_ids=tuple(disruption["unavailable_slot_ids"]),
                affected_fixture_ids=affected,
                validated_repairs=(
                    RecoveryOptionEvidence(
                        draft_id=draft_id,
                        validation_valid=workspace.drafts[draft_id].validation_report.valid,
                        diff=ScheduleDiff.model_validate(diff),
                    ),
                ),
            ),
            invocation_reason="Explain the validated minimum-change repair",
            tournament_revision=tournament.revision,
            consumed_fields=("affected_fixture_ids", "validated_repairs"),
            tool_name="read_validated_schedule_diff",
            deterministic_authority=True,
        )
        weather, recovery = await asyncio.gather(
            self._runtime.run(
                self._weather_request(
                    workspace,
                    draft_id=draft_id,
                    reason="Explain weather evidence relevant to the repair",
                )
            ),
            self._runtime.run(recovery_request),
        )
        fairness = await self._runtime.run(
            self._fairness_request(
                workspace,
                draft_id=draft_id,
                reason="Audit fairness and logistics after the repair",
            )
        )
        return tuple(
            result.model_dump(mode="json") for result in (weather, recovery, fairness)
        )
