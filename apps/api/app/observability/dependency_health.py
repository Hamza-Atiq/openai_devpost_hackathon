from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.domain.common import DomainModel, UtcDateTime


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class DependencyStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class DependencyHealth(DomainModel):
    dependency: str = Field(min_length=1, max_length=80)
    status: DependencyStatus
    circuit_state: CircuitState
    consecutive_failures: int = Field(ge=0)
    checked_at: UtcDateTime
    detail: str | None = Field(default=None, max_length=240)


class DependencyTransition(DomainModel):
    dependency: str
    from_status: DependencyStatus | None
    to_status: DependencyStatus
    circuit_state: CircuitState
    occurred_at: UtcDateTime


class DependencyHealthRegistry:
    def __init__(self) -> None:
        self._health: dict[str, DependencyHealth] = {}
        self._history: list[DependencyTransition] = []

    def record(
        self,
        *,
        dependency: str,
        status: DependencyStatus,
        circuit_state: CircuitState,
        consecutive_failures: int,
        checked_at: datetime,
        detail: str | None = None,
    ) -> DependencyHealth:
        previous = self._health.get(dependency)
        current = DependencyHealth(
            dependency=dependency,
            status=status,
            circuit_state=circuit_state,
            consecutive_failures=consecutive_failures,
            checked_at=checked_at,
            detail=detail,
        )
        self._health[dependency] = current
        if previous is None or previous.status != status or previous.circuit_state != circuit_state:
            self._history.append(
                DependencyTransition(
                    dependency=dependency,
                    from_status=None if previous is None else previous.status,
                    to_status=status,
                    circuit_state=circuit_state,
                    occurred_at=checked_at,
                )
            )
        return current

    def get(self, dependency: str) -> DependencyHealth:
        return self._health[dependency]

    @property
    def history(self) -> tuple[DependencyTransition, ...]:
        return tuple(self._history)
