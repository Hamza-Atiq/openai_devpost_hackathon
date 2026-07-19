from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from agents import RunConfig, Runner
from pydantic import Field

from app.agents.director import DirectorTurnInput, DirectorTurnOutput, create_director_agent
from app.agents.instructions import AgentEvidence, AgentOutputClaims, evaluate_output_claims
from app.agents.provider import AgentProviderRouter, ProviderRoute
from app.agents.resilience import AgentResilienceManager
from app.agents.schemas import AgentDecision, AgentMode, AgentRole, ValidationStatus
from app.api.workspace import GuestWorkspace
from app.domain.common import DomainModel
from app.observability.dependency_health import DependencyHealthRegistry


class DirectorRuntimeResult(DomainModel):
    message: str | None = None
    mode: AgentMode
    provider: str | None = None
    model: str | None = None
    proposed_state_changes: tuple[Mapping[str, object], ...] = ()
    specialist_requests: tuple[Mapping[str, object], ...] = ()
    evidence_refs: tuple[Mapping[str, object], ...] = ()
    ui_actions: tuple[Mapping[str, object], ...] = ()
    attempt_count: int = Field(ge=0)
    transitions: tuple[str, ...] = ()
    unavailable_reason: str | None = None


RunnerCall = Callable[..., Awaitable[Any]]


def _workspace_summary(workspace: GuestWorkspace) -> dict[str, object]:
    tournament = workspace.tournament
    return {
        "tournament": (
            None
            if tournament is None
            else {
                "name": tournament.name,
                "match_format_preset": tournament.match_format_preset,
                "start_date": tournament.start_date.isoformat(),
                "end_date": tournament.end_date.isoformat(),
                "team_count": len(tournament.teams),
                "venue_count": len(tournament.venues),
                "slot_count": len(tournament.slots),
                "status": tournament.status,
            }
        ),
        "constraint_confirmation": workspace.constraint_confirmation,
        "weather": {
            key: workspace.weather.get(key)
            for key in ("mode", "quality", "scenario_id")
            if key in workspace.weather
        },
        "official_version_count": len(workspace.official_versions),
        "draft_count": len(workspace.drafts),
    }


class DirectorRuntime:
    def __init__(
        self,
        *,
        provider_router: AgentProviderRouter,
        retries_allowed: Callable[[], bool] = lambda: True,
        agent_work_allowed: Callable[[], bool] = lambda: True,
        runner: RunnerCall = Runner.run,
    ) -> None:
        self._runner = runner
        self._resilience = AgentResilienceManager(
            router=provider_router,
            health=DependencyHealthRegistry(),
            timeout_seconds=10,
            max_retries=1,
            retries_allowed=retries_allowed,
            agent_work_allowed=agent_work_allowed,
        )

    async def run_turn(
        self,
        *,
        workspace: GuestWorkspace,
        user_message: str,
    ) -> DirectorRuntimeResult:
        outputs: dict[tuple[str, str], DirectorTurnOutput] = {}

        async def invoke(route: ProviderRoute) -> object:
            revision = workspace.tournament.revision if workspace.tournament is not None else 0
            turn = DirectorTurnInput(
                workspace_summary=_workspace_summary(workspace),
                tournament_revision=revision,
                user_message=user_message,
                pending_actions=(),
                mode=route.mode,
            )
            result = await self._runner(
                create_director_agent(model=route.model),
                turn.model_dump_json(),
                max_turns=8,
                run_config=RunConfig(
                    model_provider=route.sdk_provider,
                    workflow_name="CrickOps Tournament Director",
                    trace_include_sensitive_data=False,
                ),
            )
            output = DirectorTurnOutput.model_validate(result.final_output)
            contract = evaluate_output_claims(
                AgentOutputClaims(text=output.message),
                AgentEvidence(),
            )
            if not contract.valid:
                raise ValueError("director output failed the organizer-facing safety contract")
            outputs[(route.provider, route.model)] = output
            return AgentDecision(
                role=AgentRole.TOURNAMENT_DIRECTOR,
                provider=route.provider,
                model=route.model,
                occurred_at=datetime.now(UTC),
                summary=output.message[:1200],
                validation_status=ValidationStatus.VALID,
                requires_organizer_approval=bool(output.proposed_state_changes),
            )

        result = await self._resilience.run(invoke)
        if result.decision is None:
            return DirectorRuntimeResult(
                mode=AgentMode.DETERMINISTIC,
                attempt_count=result.attempt_count,
                transitions=result.transitions,
                unavailable_reason=result.deterministic.reason if result.deterministic else None,
            )
        output = outputs[(result.provider or "", result.model or "")]
        return DirectorRuntimeResult(
            message=output.message,
            mode=result.mode,
            provider=result.provider,
            model=result.model,
            proposed_state_changes=tuple(
                item.model_dump(mode="json") for item in output.proposed_state_changes
            ),
            specialist_requests=tuple(
                item.model_dump(mode="json") for item in output.specialist_requests
            ),
            evidence_refs=tuple(item.model_dump(mode="json") for item in output.evidence_refs),
            ui_actions=tuple(item.model_dump(mode="json") for item in output.ui_actions),
            attempt_count=result.attempt_count,
            transitions=result.transitions,
        )
