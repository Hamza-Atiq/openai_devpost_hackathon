from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import model_validator

from app.agents.provider import AgentProviderRouter, ProviderRoute
from app.agents.schemas import AgentDecision, AgentMode, DeterministicModeResult
from app.domain.common import DomainModel
from app.observability.dependency_health import (
    CircuitState,
    DependencyHealthRegistry,
    DependencyStatus,
)
from app.observability.recorder import observe


class ProviderOperationError(RuntimeError):
    pass


class TransientProviderError(ProviderOperationError):
    pass


class ProviderAuthenticationError(ProviderOperationError):
    pass


class ProviderValidationError(ProviderOperationError):
    pass


class UnsupportedProviderCapabilityError(ProviderOperationError):
    pass


class ResilientAgentResult(DomainModel):
    mode: AgentMode
    provider: str | None = None
    model: str | None = None
    decision: AgentDecision | None = None
    deterministic: DeterministicModeResult | None = None
    attempt_count: int
    transitions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_one_result(self) -> ResilientAgentResult:
        if (self.decision is None) == (self.deterministic is None):
            raise ValueError("result requires exactly one decision or deterministic result")
        return self


@dataclass(slots=True)
class _CircuitBreaker:
    failure_threshold: int
    recovery_after: timedelta
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: datetime | None = None

    def before_request(self, now: datetime) -> tuple[bool, bool]:
        if self.state is not CircuitState.OPEN:
            return True, False
        if self.opened_at is not None and now - self.opened_at >= self.recovery_after:
            self.state = CircuitState.HALF_OPEN
            return True, True
        return False, False

    def success(self) -> None:
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.opened_at = None

    def failure(self, now: datetime) -> None:
        self.consecutive_failures += 1
        if (
            self.state is CircuitState.HALF_OPEN
            or self.consecutive_failures >= self.failure_threshold
        ):
            self.state = CircuitState.OPEN
            self.opened_at = now


InvokeAgent = Callable[[ProviderRoute], Awaitable[object]]
Sleep = Callable[[float], Awaitable[None]]


class AgentResilienceManager:
    def __init__(
        self,
        *,
        router: AgentProviderRouter,
        health: DependencyHealthRegistry,
        timeout_seconds: float = 30,
        max_retries: int = 2,
        failure_threshold: int = 3,
        recovery_after: timedelta = timedelta(seconds=60),
        sleep: Sleep = asyncio.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        retry_jitter: Callable[[], float] = lambda: random.uniform(0, 0.1),
    ) -> None:
        if timeout_seconds <= 0 or max_retries < 0 or failure_threshold <= 0:
            raise ValueError("resilience budgets must be positive")
        self._router = router
        self._health = health
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._retry_jitter = retry_jitter
        self._breakers = {
            "openai": _CircuitBreaker(failure_threshold, recovery_after),
            "fallback": _CircuitBreaker(failure_threshold, recovery_after),
        }

    async def _attempt(
        self,
        route: ProviderRoute,
        invoke: InvokeAgent,
        breaker: _CircuitBreaker,
    ) -> tuple[AgentDecision | None, int, Exception | None]:
        attempts = 0
        last_error: Exception | None = None
        for retry in range(self._max_retries + 1):
            attempts += 1
            try:
                raw_output = await asyncio.wait_for(invoke(route), timeout=self._timeout_seconds)
                decision = route.validate_output(raw_output)
            except TimeoutError as error:
                last_error = TransientProviderError("provider request timed out")
                last_error.__cause__ = error
            except TransientProviderError as error:
                last_error = error
            except (ProviderAuthenticationError, ProviderValidationError) as error:
                last_error = error
            except UnsupportedProviderCapabilityError as error:
                last_error = error
            except (TypeError, ValueError) as error:
                last_error = ProviderValidationError("provider output failed validation")
                last_error.__cause__ = error
            else:
                breaker.success()
                self._health.record(
                    dependency=route.provider,
                    status=DependencyStatus.HEALTHY,
                    circuit_state=breaker.state,
                    consecutive_failures=0,
                    checked_at=self._clock(),
                )
                observe(
                    component="provider",
                    event="dependency_transition",
                    outcome="healthy",
                    metadata={
                        "provider": route.provider,
                        "model": route.model,
                        "circuit_state": breaker.state,
                    },
                )
                return decision, attempts, None

            breaker.failure(self._clock())
            status = (
                DependencyStatus.UNAVAILABLE
                if breaker.state is CircuitState.OPEN
                else DependencyStatus.DEGRADED
            )
            self._health.record(
                dependency=route.provider,
                status=status,
                circuit_state=breaker.state,
                consecutive_failures=breaker.consecutive_failures,
                checked_at=self._clock(),
                detail=type(last_error).__name__,
            )
            observe(
                component="provider",
                event="dependency_transition",
                outcome=status,
                metadata={
                    "provider": route.provider,
                    "model": route.model,
                    "circuit_state": breaker.state,
                    "error_type": type(last_error).__name__,
                },
            )
            transient = isinstance(last_error, TransientProviderError)
            if not transient or breaker.state is CircuitState.OPEN or retry == self._max_retries:
                break
            await self._sleep(0.25 * (2**retry) + self._retry_jitter())
        return None, attempts, last_error

    async def run(self, invoke: InvokeAgent) -> ResilientAgentResult:
        transitions: list[str] = []
        attempt_count = 0
        primary = self._router.primary()
        primary_breaker = self._breakers["openai"]
        primary_allowed, half_open = primary_breaker.before_request(self._clock())
        if half_open:
            transitions.append("primary_half_open")
        if primary_allowed:
            decision, attempts, _error = await self._attempt(primary, invoke, primary_breaker)
            attempt_count += attempts
            if decision is not None:
                transitions.append("primary_active")
                result = ResilientAgentResult(
                    mode=primary.mode,
                    provider=primary.provider,
                    model=primary.model,
                    decision=decision,
                    attempt_count=attempt_count,
                    transitions=tuple(transitions),
                )
                observe(
                    component="agent",
                    event="provider_route",
                    outcome=result.mode,
                    metadata={
                        "provider": result.provider,
                        "model": result.model,
                        "attempt_count": result.attempt_count,
                        "transitions": result.transitions,
                    },
                )
                return result
        else:
            transitions.append("primary_circuit_open")

        try:
            fallback = self._router.fallback()
        except RuntimeError:
            fallback = None
        if fallback is not None:
            transitions.append("fallback_attempted")
            fallback_breaker = self._breakers["fallback"]
            fallback_allowed, _ = fallback_breaker.before_request(self._clock())
            if fallback_allowed:
                decision, attempts, _error = await self._attempt(fallback, invoke, fallback_breaker)
                attempt_count += attempts
                if decision is not None:
                    transitions.append("fallback_active")
                    result = ResilientAgentResult(
                        mode=fallback.mode,
                        provider=fallback.provider,
                        model=fallback.model,
                        decision=decision,
                        attempt_count=attempt_count,
                        transitions=tuple(transitions),
                    )
                    observe(
                        component="agent",
                        event="provider_route",
                        outcome=result.mode,
                        metadata={
                            "provider": result.provider,
                            "model": result.model,
                            "attempt_count": result.attempt_count,
                            "transitions": result.transitions,
                        },
                    )
                    return result

        transitions.append("deterministic_active")
        result = ResilientAgentResult(
            mode=AgentMode.DETERMINISTIC,
            deterministic=self._router.deterministic_result(
                "Conversational interpretation and narrative explanations are unavailable."
            ),
            attempt_count=attempt_count,
            transitions=tuple(transitions),
        )
        observe(
            component="agent",
            event="provider_route",
            outcome=result.mode,
            metadata={
                "provider": None,
                "model": None,
                "attempt_count": result.attempt_count,
                "transitions": result.transitions,
                "fabricated_response": False,
            },
        )
        return result
