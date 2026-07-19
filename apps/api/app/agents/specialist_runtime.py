from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from agents import RunConfig, Runner
from pydantic import Field

from app.agents.fairness import (
    FairnessAuditInput,
    FairnessAuditOutput,
    create_fairness_agent,
    validate_fairness_audit,
)
from app.agents.provider import AgentProviderRouter, ProviderRoute
from app.agents.recovery import (
    RecoveryInput,
    RecoveryOutput,
    create_recovery_agent,
    validate_recovery_output,
)
from app.agents.resilience import AgentResilienceManager
from app.agents.rules import (
    ConstraintInterpretationInput,
    ConstraintInterpretationOutput,
    create_rules_agent,
    validate_constraint_interpretation,
)
from app.agents.schemas import (
    AgentDecision,
    AgentMode,
    AgentRole,
    ToolOutcome,
    ToolOutcomeStatus,
    ValidationStatus,
)
from app.agents.strategy import (
    StrategyInput,
    StrategyOutput,
    create_strategy_agent,
    validate_strategy_output,
)
from app.agents.weather import (
    WeatherAnalysisInput,
    WeatherAnalysisOutput,
    create_weather_agent,
    validate_weather_analysis,
)
from app.domain.common import DomainModel
from app.observability.dependency_health import DependencyHealthRegistry

SpecialistInput = (
    ConstraintInterpretationInput
    | StrategyInput
    | WeatherAnalysisInput
    | FairnessAuditInput
    | RecoveryInput
)
SpecialistOutput = (
    ConstraintInterpretationOutput
    | StrategyOutput
    | WeatherAnalysisOutput
    | FairnessAuditOutput
    | RecoveryOutput
)


class SpecialistRunRequest(DomainModel):
    role: AgentRole
    payload: SpecialistInput
    invocation_reason: str = Field(min_length=1, max_length=500)
    tournament_revision: int = Field(ge=0)
    consumed_fields: tuple[str, ...] = Field(min_length=1)
    tool_name: str = Field(min_length=1, max_length=120)
    deterministic_authority: bool


class SpecialistRuntimeResult(DomainModel):
    available: bool
    role: AgentRole
    mode: AgentMode
    provider: str | None = None
    model: str | None = None
    occurred_at: datetime
    tournament_revision: int
    invocation_reason: str
    validation_status: ValidationStatus
    evidence_refs: tuple[Mapping[str, object], ...] = ()
    tool_outcomes: tuple[ToolOutcome, ...] = ()
    consumed_fields: tuple[str, ...] = ()
    output: Mapping[str, object] = Field(default_factory=dict)
    organizer_summary: str
    attempt_count: int = Field(ge=0)
    transitions: tuple[str, ...] = ()


RunnerCall = Callable[..., Awaitable[Any]]


def _digest(output: SpecialistOutput) -> str:
    canonical = json.dumps(
        output.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _summary(output: SpecialistOutput) -> str:
    if isinstance(output, ConstraintInterpretationOutput):
        return output.clarification_question or (
            f"Interpreted {len(output.proposed_additions) + len(output.proposed_changes)} "
            "constraint proposals."
        )
    if isinstance(output, StrategyOutput):
        return output.comparison_commentary or (
            f"Prepared {len(output.profile_requests)} scheduling profile requests."
        )
    if isinstance(output, WeatherAnalysisOutput):
        return (
            f"Assessed forecast-based risk for {len(output.high_risk_fixtures)} "
            "high-risk fixtures."
        )
    if isinstance(output, FairnessAuditOutput):
        return output.overall_summary
    return output.escalation or (
        f"Explained {len(output.option_explanations)} validated recovery options."
    )


SpecialistDefinition = tuple[
    Callable[..., object], type[DomainModel], Callable[..., object], int
]

_FACTORIES: dict[AgentRole, SpecialistDefinition] = {
    AgentRole.RULES_CONSTRAINT: (
        create_rules_agent,
        ConstraintInterpretationOutput,
        validate_constraint_interpretation,
        4,
    ),
    AgentRole.SCHEDULING_STRATEGY: (
        create_strategy_agent,
        StrategyOutput,
        validate_strategy_output,
        4,
    ),
    AgentRole.WEATHER_INTELLIGENCE: (
        create_weather_agent,
        WeatherAnalysisOutput,
        validate_weather_analysis,
        4,
    ),
    AgentRole.FAIRNESS_LOGISTICS: (
        create_fairness_agent,
        FairnessAuditOutput,
        validate_fairness_audit,
        3,
    ),
    AgentRole.DISRUPTION_RECOVERY: (
        create_recovery_agent,
        RecoveryOutput,
        validate_recovery_output,
        5,
    ),
}


class SpecialistRuntime:
    def __init__(
        self,
        *,
        provider_router: AgentProviderRouter,
        runner: RunnerCall = Runner.run,
        retries_allowed: Callable[[], bool] = lambda: True,
        agent_work_allowed: Callable[[], bool] = lambda: True,
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

    @staticmethod
    def supported_roles() -> tuple[AgentRole, ...]:
        return tuple(_FACTORIES)

    async def run(self, request: SpecialistRunRequest) -> SpecialistRuntimeResult:
        if request.role not in _FACTORIES:
            raise ValueError("the Tournament Director is not a specialist runtime role")
        factory, output_type, validator, max_turns = _FACTORIES[request.role]
        outputs: dict[tuple[str, str], SpecialistOutput] = {}
        tool_outcomes: dict[tuple[str, str], ToolOutcome] = {}

        async def invoke(route: ProviderRoute) -> object:
            result = await self._runner(
                factory(model=route.model),
                request.payload.model_dump_json(),
                max_turns=max_turns,
                run_config=RunConfig(
                    model_provider=route.sdk_provider,
                    workflow_name=f"CrickOps {request.role.value}",
                    trace_include_sensitive_data=False,
                ),
            )
            output = output_type.model_validate(result.final_output)
            validated = validator(request.payload, output)
            consumed = {
                field
                for evidence in validated.evidence_refs
                for field in evidence.consumed_fields
            }
            if not set(request.consumed_fields).issubset(consumed):
                raise ValueError("specialist invocation consumed no role-specific evidence")
            outcome = ToolOutcome(
                tool_name=request.tool_name,
                status=ToolOutcomeStatus.VALIDATED,
                deterministic_authority=request.deterministic_authority,
                validation_status=ValidationStatus.VALID,
                output_digest=_digest(validated),
            )
            outputs[(route.provider, route.model)] = validated
            tool_outcomes[(route.provider, route.model)] = outcome
            return AgentDecision(
                role=request.role,
                provider=route.provider,
                model=route.model,
                occurred_at=datetime.now(UTC),
                summary=_summary(validated)[:1200],
                validation_status=ValidationStatus.VALID,
                requires_organizer_approval=False,
                tool_outcomes=(outcome,),
            )

        resilient = await self._resilience.run(invoke)
        occurred_at = datetime.now(UTC)
        if resilient.decision is None:
            return SpecialistRuntimeResult(
                available=False,
                role=request.role,
                mode=AgentMode.DETERMINISTIC,
                occurred_at=occurred_at,
                tournament_revision=request.tournament_revision,
                invocation_reason=request.invocation_reason,
                validation_status=ValidationStatus.NOT_APPLICABLE,
                organizer_summary=(
                    resilient.deterministic.reason
                    if resilient.deterministic is not None
                    else "Specialist explanation is unavailable."
                ),
                attempt_count=resilient.attempt_count,
                transitions=resilient.transitions,
            )

        key = (resilient.provider or "", resilient.model or "")
        output = outputs[key]
        outcome = tool_outcomes[key]
        return SpecialistRuntimeResult(
            available=True,
            role=request.role,
            mode=resilient.mode,
            provider=resilient.provider,
            model=resilient.model,
            occurred_at=resilient.decision.occurred_at,
            tournament_revision=request.tournament_revision,
            invocation_reason=request.invocation_reason,
            validation_status=ValidationStatus.VALID,
            evidence_refs=tuple(
                evidence.model_dump(mode="json") for evidence in output.evidence_refs
            ),
            tool_outcomes=(outcome,),
            consumed_fields=request.consumed_fields,
            output=output.model_dump(mode="json"),
            organizer_summary=resilient.decision.summary,
            attempt_count=resilient.attempt_count,
            transitions=resilient.transitions,
        )
