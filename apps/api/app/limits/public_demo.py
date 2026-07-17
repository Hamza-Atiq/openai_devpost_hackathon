from __future__ import annotations

import hashlib
import hmac
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from threading import RLock

from app.observability.recorder import observe


class UsageAction(StrEnum):
    GENERATION = "generation"
    REPAIR = "repair"
    AGENT = "agent"
    WEATHER = "weather"


class BudgetMode(StrEnum):
    NORMAL = "normal"
    CONSERVE = "conserve"
    DETERMINISTIC = "deterministic"


@dataclass(frozen=True, slots=True)
class DemoLimits:
    active_jobs_per_workspace: int = 1
    generation_requests_per_workspace_24h: int = 12
    repair_requests_per_workspace_24h: int = 12
    agent_calls_per_workspace_24h: int = 80
    agent_calls_per_ip_24h: int = 300
    weather_refreshes_per_workspace_24h: int = 60
    concurrent_solver_jobs_per_worker: int = 4
    queued_jobs_per_workspace: int = 1
    provider_daily_budget_usd: int | float | Decimal = 50

    def __post_init__(self) -> None:
        numeric = (
            self.active_jobs_per_workspace,
            self.generation_requests_per_workspace_24h,
            self.repair_requests_per_workspace_24h,
            self.agent_calls_per_workspace_24h,
            self.agent_calls_per_ip_24h,
            self.weather_refreshes_per_workspace_24h,
            self.concurrent_solver_jobs_per_worker,
            self.queued_jobs_per_workspace,
        )
        if any(not isinstance(value, int) or value < 0 for value in numeric):
            raise ValueError("public-demo count limits must be non-negative integers")
        if Decimal(str(self.provider_daily_budget_usd)) <= 0:
            raise ValueError("provider daily budget must be greater than zero")


@dataclass(frozen=True, slots=True)
class LimitDecision:
    allowed: bool
    action: str
    limit_name: str | None = None
    reset_at: datetime | None = None
    remaining: int | None = None


@dataclass(frozen=True, slots=True)
class AbuseRecord:
    workspace_pseudonym: str | None
    ip_pseudonym: str | None
    action: str
    timestamp: datetime
    limit_name: str
    reset_at: datetime | None
    counter_value: int | None
    limit_value: int | float | None


_WORKSPACE_LIMITS = {
    UsageAction.GENERATION: "generation_requests_per_workspace_24h",
    UsageAction.REPAIR: "repair_requests_per_workspace_24h",
    UsageAction.AGENT: "agent_calls_per_workspace_24h",
    UsageAction.WEATHER: "weather_refreshes_per_workspace_24h",
}


class PublicDemoProtection:
    """Thread-safe limits for an anonymous, publicly accessible demonstration."""

    _window = timedelta(hours=24)

    def __init__(
        self,
        *,
        limits: DemoLimits | None = None,
        clock: Callable[[], datetime] | None = None,
        pseudonym_salt: bytes,
        max_abuse_records: int = 1_000,
    ) -> None:
        if len(pseudonym_salt) < 16:
            raise ValueError("pseudonym salt must contain at least 16 bytes")
        if max_abuse_records < 1:
            raise ValueError("max_abuse_records must be positive")
        self.limits = limits or DemoLimits()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._salt = bytes(pseudonym_salt)
        self._workspace_events: dict[tuple[UsageAction, str], deque[datetime]] = defaultdict(deque)
        self._ip_agent_events: dict[str, deque[datetime]] = defaultdict(deque)
        self._active_jobs: dict[str, int] = defaultdict(int)
        self._global_active_jobs = 0
        self._queued_jobs: dict[str, int] = defaultdict(int)
        self._abuse_records: deque[AbuseRecord] = deque(maxlen=max_abuse_records)
        self._provider_spend = Decimal("0")
        self._budget_day: date | None = None
        self._emergency_deterministic = False
        self._lock = RLock()

    @property
    def abuse_records(self) -> tuple[AbuseRecord, ...]:
        with self._lock:
            return tuple(self._abuse_records)

    @property
    def budget_mode(self) -> BudgetMode:
        with self._lock:
            self._roll_budget_day(self._now())
            if self._emergency_deterministic:
                return BudgetMode.DETERMINISTIC
            ratio = self._provider_spend / Decimal(str(self.limits.provider_daily_budget_usd))
            if ratio >= 1:
                return BudgetMode.DETERMINISTIC
            if ratio >= Decimal("0.75"):
                return BudgetMode.CONSERVE
            return BudgetMode.NORMAL

    @property
    def nonessential_retries_allowed(self) -> bool:
        return self.budget_mode is BudgetMode.NORMAL

    @property
    def agent_work_allowed(self) -> bool:
        return self.budget_mode is not BudgetMode.DETERMINISTIC

    def consume(
        self,
        action: UsageAction,
        *,
        workspace_id: str,
        ip_address: str | None,
    ) -> LimitDecision:
        now = self._now()
        with self._lock:
            if action is UsageAction.AGENT and not self.agent_work_allowed:
                return self._deny(
                    action=action.value,
                    limit_name="provider_daily_budget_usd",
                    workspace_id=workspace_id,
                    ip_address=ip_address,
                    now=now,
                    reset_at=self._next_utc_day(now),
                    counter_value=None,
                    limit_value=float(self.limits.provider_daily_budget_usd),
                )

            limit_name = _WORKSPACE_LIMITS[action]
            limit = int(getattr(self.limits, limit_name))
            events = self._workspace_events[(action, workspace_id)]
            self._prune(events, now)
            if len(events) >= limit:
                reset_at = events[0] + self._window if events else now + self._window
                return self._deny(
                    action=action.value,
                    limit_name=limit_name,
                    workspace_id=workspace_id,
                    ip_address=ip_address,
                    now=now,
                    reset_at=reset_at,
                    counter_value=len(events),
                    limit_value=limit,
                )

            ip_events: deque[datetime] | None = None
            if action is UsageAction.AGENT and ip_address:
                ip_events = self._ip_agent_events[ip_address]
                self._prune(ip_events, now)
                if len(ip_events) >= self.limits.agent_calls_per_ip_24h:
                    return self._deny(
                        action=action.value,
                        limit_name="agent_calls_per_ip_24h",
                        workspace_id=workspace_id,
                        ip_address=ip_address,
                        now=now,
                        reset_at=ip_events[0] + self._window,
                        counter_value=len(ip_events),
                        limit_value=self.limits.agent_calls_per_ip_24h,
                    )

            events.append(now)
            if ip_events is not None:
                ip_events.append(now)
            return LimitDecision(
                allowed=True,
                action=action.value,
                remaining=limit - len(events),
            )

    def acquire_job(self, workspace_id: str) -> LimitDecision:
        now = self._now()
        with self._lock:
            if self._active_jobs[workspace_id] >= self.limits.active_jobs_per_workspace:
                return self._deny(
                    action="solver_job",
                    limit_name="active_jobs_per_workspace",
                    workspace_id=workspace_id,
                    ip_address=None,
                    now=now,
                    reset_at=None,
                    counter_value=self._active_jobs[workspace_id],
                    limit_value=self.limits.active_jobs_per_workspace,
                )
            if self._global_active_jobs >= self.limits.concurrent_solver_jobs_per_worker:
                return self._deny(
                    action="solver_job",
                    limit_name="concurrent_solver_jobs_per_worker",
                    workspace_id=workspace_id,
                    ip_address=None,
                    now=now,
                    reset_at=None,
                    counter_value=self._global_active_jobs,
                    limit_value=self.limits.concurrent_solver_jobs_per_worker,
                )
            self._active_jobs[workspace_id] += 1
            self._global_active_jobs += 1
            return LimitDecision(allowed=True, action="solver_job")

    def enqueue_job(self, workspace_id: str) -> LimitDecision:
        """Reserve bounded queue capacity for an asynchronous solver worker."""
        now = self._now()
        with self._lock:
            queued = self._queued_jobs[workspace_id]
            if queued >= self.limits.queued_jobs_per_workspace:
                return self._deny(
                    action="solver_queue",
                    limit_name="queued_jobs_per_workspace",
                    workspace_id=workspace_id,
                    ip_address=None,
                    now=now,
                    reset_at=None,
                    counter_value=queued,
                    limit_value=self.limits.queued_jobs_per_workspace,
                )
            self._queued_jobs[workspace_id] += 1
            return LimitDecision(
                allowed=True,
                action="solver_queue",
                remaining=self.limits.queued_jobs_per_workspace - queued - 1,
            )

    def dequeue_job(self, workspace_id: str) -> None:
        with self._lock:
            queued = self._queued_jobs.get(workspace_id, 0)
            if queued <= 1:
                self._queued_jobs.pop(workspace_id, None)
            else:
                self._queued_jobs[workspace_id] = queued - 1

    def release_job(self, workspace_id: str) -> None:
        with self._lock:
            active = self._active_jobs.get(workspace_id, 0)
            if active <= 0:
                return
            if active == 1:
                self._active_jobs.pop(workspace_id, None)
            else:
                self._active_jobs[workspace_id] = active - 1
            self._global_active_jobs = max(0, self._global_active_jobs - 1)

    def record_provider_cost(self, usd: int | float | Decimal) -> BudgetMode:
        amount = Decimal(str(usd))
        if amount < 0:
            raise ValueError("provider cost cannot be negative")
        with self._lock:
            now = self._now()
            self._roll_budget_day(now)
            previous = self.budget_mode
            self._provider_spend += amount
            current = self.budget_mode
            if current is not previous:
                observe(
                    component="quota",
                    event="provider_budget_mode_changed",
                    outcome=current.value,
                    metadata={"mode": current.value},
                )
            return current

    def reset_daily_budget(self) -> None:
        with self._lock:
            self._provider_spend = Decimal("0")
            self._budget_day = self._now().date()

    def set_emergency_deterministic(self, enabled: bool) -> None:
        with self._lock:
            self._emergency_deterministic = enabled
        observe(
            component="quota",
            event="emergency_deterministic_changed",
            outcome="enabled" if enabled else "disabled",
        )

    def _deny(
        self,
        *,
        action: str,
        limit_name: str,
        workspace_id: str | None,
        ip_address: str | None,
        now: datetime,
        reset_at: datetime | None,
        counter_value: int | None,
        limit_value: int | float | None,
    ) -> LimitDecision:
        workspace_pseudonym = self._pseudonym("workspace", workspace_id)
        ip_pseudonym = self._pseudonym("ip", ip_address)
        record = AbuseRecord(
            workspace_pseudonym=workspace_pseudonym,
            ip_pseudonym=ip_pseudonym,
            action=action,
            timestamp=now,
            limit_name=limit_name,
            reset_at=reset_at,
            counter_value=counter_value,
            limit_value=limit_value,
        )
        self._abuse_records.append(record)
        observe(
            component="quota",
            event="request_denied",
            outcome="limited",
            metadata={
                "action": action,
                "limit_name": limit_name,
                "workspace_pseudonym": workspace_pseudonym,
                "ip_pseudonym": ip_pseudonym,
                "reset_at": reset_at,
                "counter_value": counter_value,
                "limit_value": limit_value,
            },
        )
        return LimitDecision(
            allowed=False,
            action=action,
            limit_name=limit_name,
            reset_at=reset_at,
            remaining=0,
        )

    def _pseudonym(self, kind: str, value: str | None) -> str | None:
        if value is None:
            return None
        digest = hmac.new(self._salt, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()
        return digest[:20]

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("public-demo clock must return a timezone-aware datetime")
        return value.astimezone(UTC)

    def _prune(self, events: deque[datetime], now: datetime) -> None:
        cutoff = now - self._window
        while events and events[0] <= cutoff:
            events.popleft()

    def _roll_budget_day(self, now: datetime) -> None:
        if self._budget_day != now.date():
            self._budget_day = now.date()
            self._provider_spend = Decimal("0")

    @staticmethod
    def _next_utc_day(now: datetime) -> datetime:
        return datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
