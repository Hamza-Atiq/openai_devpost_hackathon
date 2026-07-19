from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from agents import RunConfig, Runner
from pydantic import Field

from app.agents.director import (
    DirectorTurnInput,
    DirectorTurnOutput,
    SpecialistRequest,
    create_director_agent,
)
from app.agents.instructions import AgentEvidence, AgentOutputClaims, evaluate_output_claims
from app.agents.provider import AgentProviderRouter, ProviderRoute
from app.agents.resilience import AgentResilienceManager
from app.agents.schemas import AgentDecision, AgentMode, AgentRole, ValidationStatus
from app.agents.specialist_runtime import (
    SpecialistRunRequest,
    SpecialistRuntimeResult,
)
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
    specialist_evidence: tuple[Mapping[str, object], ...] = ()
    evidence_refs: tuple[Mapping[str, object], ...] = ()
    ui_actions: tuple[Mapping[str, object], ...] = ()
    attempt_count: int = Field(ge=0)
    transitions: tuple[str, ...] = ()
    unavailable_reason: str | None = None


RunnerCall = Callable[..., Awaitable[Any]]


class SpecialistRuntimeProtocol(Protocol):
    async def run(self, request: SpecialistRunRequest) -> SpecialistRuntimeResult: ...


SpecialistRequestBuilder = Callable[
    [GuestWorkspace, object, str], SpecialistRunRequest | None
]


def normalize_specialist_requests(
    requests: tuple[SpecialistRequest, ...],
    *,
    workspace: GuestWorkspace,
    user_message: str,
) -> tuple[SpecialistRequest, ...]:
    lowered = user_message.casefold()
    asks_for_comparison = any(
        word in lowered for word in ("option", "profile", "schedule")
    ) and any(
        word in lowered
        for word in ("lowest", "highest", "compare", "best", "risk", "fairness")
    )
    roles = {request.role for request in requests}
    if (
        asks_for_comparison
        and workspace.schedule_runs
        and AgentRole.SCHEDULING_STRATEGY not in roles
    ):
        return (
            *requests,
            SpecialistRequest(
                role=AgentRole.SCHEDULING_STRATEGY,
                reason="Compare schedule options using validated solver metrics",
                required_evidence=("validated_schedule_comparison",),
            ),
        )
    return requests


def _workspace_summary(workspace: GuestWorkspace) -> dict[str, object]:
    tournament = workspace.tournament
    latest_run = next(reversed(tuple(workspace.schedule_runs.values())), None)
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
        "latest_validated_options": (
            latest_run.get("options", ())
            if latest_run is not None and latest_run.get("status") == "completed"
            else ()
        ),
    }


class DirectorRuntime:
    def __init__(
        self,
        *,
        provider_router: AgentProviderRouter,
        retries_allowed: Callable[[], bool] = lambda: True,
        agent_work_allowed: Callable[[], bool] = lambda: True,
        runner: RunnerCall = Runner.run,
        specialist_runtime: SpecialistRuntimeProtocol | None = None,
        specialist_request_builder: SpecialistRequestBuilder | None = None,
    ) -> None:
        self._runner = runner
        self._specialist_runtime = specialist_runtime
        self._specialist_request_builder = specialist_request_builder
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
        routes: dict[tuple[str, str], ProviderRoute] = {}

        async def run_director(
            route: ProviderRoute,
            specialist_evidence: tuple[Mapping[str, object], ...] = (),
        ) -> DirectorTurnOutput:
            revision = workspace.tournament.revision if workspace.tournament is not None else 0
            turn = DirectorTurnInput(
                workspace_summary=_workspace_summary(workspace),
                tournament_revision=revision,
                user_message=user_message,
                pending_actions=(),
                mode=route.mode,
                specialist_evidence=specialist_evidence,
            )
            runner_result = await self._runner(
                create_director_agent(model=route.model),
                turn.model_dump_json(),
                max_turns=8,
                run_config=RunConfig(
                    model_provider=route.sdk_provider,
                    workflow_name="CrickOps Tournament Director",
                    trace_include_sensitive_data=False,
                ),
            )
            output = DirectorTurnOutput.model_validate(runner_result.final_output)
            contract = evaluate_output_claims(
                AgentOutputClaims(text=output.message),
                AgentEvidence(),
            )
            if not contract.valid:
                raise ValueError("director output failed the organizer-facing safety contract")
            return output

        async def invoke(route: ProviderRoute) -> object:
            output = await run_director(route)
            outputs[(route.provider, route.model)] = output
            routes[(route.provider, route.model)] = route
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
        specialist_evidence: tuple[Mapping[str, object], ...] = ()
        requested_specialists = normalize_specialist_requests(
            output.specialist_requests,
            workspace=workspace,
            user_message=user_message,
        )
        if (
            requested_specialists
            and self._specialist_runtime is not None
            and self._specialist_request_builder is not None
        ):
            collected: list[Mapping[str, object]] = []
            for specialist_request in requested_specialists:
                request = self._specialist_request_builder(
                    workspace, specialist_request, user_message
                )
                if request is None:
                    continue
                specialist_result = await self._specialist_runtime.run(request)
                collected.append(specialist_result.model_dump(mode="json"))
            if collected:
                specialist_evidence = tuple(collected)
                output = await run_director(
                    routes[(result.provider or "", result.model or "")],
                    specialist_evidence,
                )
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
            specialist_evidence=specialist_evidence,
            evidence_refs=tuple(item.model_dump(mode="json") for item in output.evidence_refs),
            ui_actions=tuple(item.model_dump(mode="json") for item in output.ui_actions),
            attempt_count=result.attempt_count,
            transitions=result.transitions,
        )
