from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from agents import ModelProvider
from app.agents.provider import (
    AgentProviderRouter,
    ProviderCapabilities,
    ProviderRegistration,
)
from app.agents.resilience import (
    AgentResilienceManager,
    ProviderValidationError,
    TransientProviderError,
)
from app.agents.schemas import AgentMode
from app.observability.context import observation_scope
from app.observability.dependency_health import CircuitState, DependencyHealthRegistry
from app.observability.recorder import ObservabilityRecorder


class StubFallbackProvider(ModelProvider):
    def get_model(self, model_name: str | None):
        raise NotImplementedError


def _router(*, fallback: bool = True) -> AgentProviderRouter:
    registration = None
    if fallback:
        registration = ProviderRegistration(
            provider="configured-fallback",
            model="provider-model-v1",
            capabilities=ProviderCapabilities(
                structured_outputs=True,
                function_tools=True,
                validation_gate=True,
                approval_gate=True,
                hard_constraint_protection=True,
            ),
            sdk_provider=StubFallbackProvider(),
        )
    return AgentProviderRouter(
        openai_api_key="test-key-long-enough",
        fallback=registration,
    )


def _decision(provider: str, model: str) -> dict[str, object]:
    return {
        "role": "tournament_director",
        "provider": provider,
        "model": model,
        "occurred_at": datetime(2026, 7, 16, 14, tzinfo=UTC),
        "summary": "Validated options are ready.",
        "validation_status": "valid",
        "requires_organizer_approval": True,
    }


async def _no_sleep(_seconds: float) -> None:
    return None


def test_transient_primary_failures_retry_then_use_fallback_with_visible_provenance() -> None:
    events: list[str] = []
    recorder = ObservabilityRecorder()

    async def invoke(route):
        events.append(f"call:{route.provider}")
        if route.provider == "openai":
            raise TransientProviderError("temporary 503")
        return _decision(route.provider, route.model)

    with observation_scope("018f6c7a-9a4b-7c1d-8e2f-123456789abc", recorder):
        result = asyncio.run(
            AgentResilienceManager(
                router=_router(),
                health=DependencyHealthRegistry(),
                sleep=_no_sleep,
                retry_jitter=lambda: 0,
            ).run(invoke)
        )

    assert events == ["call:openai"] * 3 + ["call:configured-fallback"]
    assert result.mode is AgentMode.FALLBACK_MODEL
    assert result.provider == "configured-fallback"
    assert result.model == "provider-model-v1"
    assert result.decision is not None
    assert result.attempt_count == 4
    agent_records = recorder.records_for("018f6c7a-9a4b-7c1d-8e2f-123456789abc")
    assert agent_records[-1].component == "agent"
    assert agent_records[-1].outcome == "fallback-model"
    assert agent_records[-1].metadata["provider"] == "configured-fallback"
    assert agent_records[-1].metadata["attempt_count"] == 4


def test_all_provider_outages_return_non_fabricated_deterministic_mode() -> None:
    async def invoke(_route):
        raise TransientProviderError("offline")

    result = asyncio.run(
        AgentResilienceManager(
            router=_router(),
            health=DependencyHealthRegistry(),
            sleep=_no_sleep,
            retry_jitter=lambda: 0,
        ).run(invoke)
    )

    assert result.mode is AgentMode.DETERMINISTIC
    assert result.decision is None
    assert result.deterministic is not None
    assert result.deterministic.fabricated_response is False


def test_validation_failure_is_not_retried_before_safe_fallback() -> None:
    primary_calls = 0

    async def invoke(route):
        nonlocal primary_calls
        if route.provider == "openai":
            primary_calls += 1
            raise ProviderValidationError("invalid schema")
        return _decision(route.provider, route.model)

    result = asyncio.run(
        AgentResilienceManager(
            router=_router(),
            health=DependencyHealthRegistry(),
            sleep=_no_sleep,
        ).run(invoke)
    )

    assert primary_calls == 1
    assert result.mode is AgentMode.FALLBACK_MODEL


def test_timeout_is_bounded_and_falls_back() -> None:
    async def invoke(route):
        if route.provider == "openai":
            await asyncio.sleep(0.02)
        return _decision(route.provider, route.model)

    result = asyncio.run(
        AgentResilienceManager(
            router=_router(),
            health=DependencyHealthRegistry(),
            timeout_seconds=0.001,
            max_retries=0,
            sleep=_no_sleep,
        ).run(invoke)
    )

    assert result.mode is AgentMode.FALLBACK_MODEL
    assert result.attempt_count == 2


def test_open_circuit_half_opens_and_recovers_primary_automatically() -> None:
    now = datetime(2026, 7, 16, 14, tzinfo=UTC)
    clock_value = [now]
    should_fail = [True]
    health = DependencyHealthRegistry()

    async def invoke(route):
        if should_fail[0]:
            raise TransientProviderError("offline")
        return _decision(route.provider, route.model)

    manager = AgentResilienceManager(
        router=_router(fallback=False),
        health=health,
        sleep=_no_sleep,
        clock=lambda: clock_value[0],
        failure_threshold=1,
        recovery_after=timedelta(seconds=30),
    )
    first = asyncio.run(manager.run(invoke))
    assert first.mode is AgentMode.DETERMINISTIC
    assert health.get("openai").circuit_state is CircuitState.OPEN

    clock_value[0] += timedelta(seconds=31)
    should_fail[0] = False
    recovered = asyncio.run(manager.run(invoke))

    assert recovered.mode is AgentMode.GPT_5_6
    assert health.get("openai").circuit_state is CircuitState.CLOSED
    assert "primary_half_open" in recovered.transitions
