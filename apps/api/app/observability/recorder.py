from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from threading import Lock
from typing import Any

from app.observability.context import current_correlation_id, current_recorder

_LOGGER = logging.getLogger("crickops.observability")

_SENSITIVE_KEY_PARTS = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "hidden_reasoning",
        "password",
        "raw_prompt",
        "secret",
        "stack_trace",
        "token",
    }
)


def _sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return any(
        normalized == part or normalized.endswith(f"_{part}") for part in _SENSITIVE_KEY_PARTS
    )


def redact_metadata(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): redact_metadata(item)
            for key, item in value.items()
            if not _sensitive_key(key)
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [redact_metadata(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str) and len(value) > 240:
        return f"[text omitted; {len(value)} characters]"
    return value


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    correlation_id: str
    component: str
    event: str
    outcome: str
    metadata: Mapping[str, object]
    occurred_at: datetime


class ObservabilityRecorder:
    def __init__(self) -> None:
        self._records: list[ObservationRecord] = []
        self._metrics: defaultdict[str, float] = defaultdict(float)
        self._lock = Lock()

    def record(
        self,
        *,
        component: str,
        event: str,
        outcome: str,
        metadata: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> ObservationRecord:
        record = ObservationRecord(
            correlation_id=correlation_id or current_correlation_id(),
            component=component,
            event=event,
            outcome=outcome.value if isinstance(outcome, Enum) else str(outcome),
            metadata=redact_metadata(metadata or {}),
            occurred_at=datetime.now(UTC),
        )
        with self._lock:
            self._records.append(record)
            self._update_metrics(record)
        _LOGGER.info(
            json.dumps(
                {
                    "correlation_id": record.correlation_id,
                    "component": record.component,
                    "event": record.event,
                    "outcome": record.outcome,
                    "metadata": record.metadata,
                    "occurred_at": record.occurred_at.isoformat(),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return record

    def _update_metrics(self, record: ObservationRecord) -> None:
        metric = {
            "agent": "agent_runs_total",
            "tool": "tool_invocations_total",
            "solver": "solver_runs_total",
            "weather": "weather_fetches_total",
            "approval": "approvals_total",
            "audit": "audit_events_total",
        }.get(record.component)
        if metric:
            self._metrics[metric] += 1
        if record.component == "validator" and record.outcome not in {"valid", "success"}:
            self._metrics["validation_failures_total"] += 1
        if record.component == "http":
            self._metrics["http_requests_total"] += 1
            duration = record.metadata.get("duration_ms")
            if isinstance(duration, int | float):
                self._metrics["http_request_duration_ms"] = float(duration)
            if record.outcome == "error":
                self._metrics["http_errors_total"] += 1
        if record.component == "solver":
            duration = record.metadata.get("duration_ms")
            if isinstance(duration, int | float):
                self._metrics["solver_duration_ms"] = float(duration)
        if record.component == "agent" and record.outcome == "fallback-model":
            self._metrics["provider_fallbacks_total"] += 1
        if record.component == "approval" and record.outcome == "conflict":
            self._metrics["approval_conflicts_total"] += 1
        if record.component == "workspace" and record.event == "expired":
            self._metrics["workspace_expirations_total"] += 1
        if record.component == "hero" and record.outcome == "success":
            self._metrics["hero_flow_success_total"] += 1

    def records_for(self, correlation_id: str) -> tuple[ObservationRecord, ...]:
        with self._lock:
            return tuple(
                record for record in self._records if record.correlation_id == correlation_id
            )

    def metric(self, name: str) -> float:
        with self._lock:
            return self._metrics[name]


def observe(
    *,
    component: str,
    event: str,
    outcome: str,
    metadata: Mapping[str, Any] | None = None,
) -> ObservationRecord | None:
    recorder = current_recorder()
    if recorder is None:
        return None
    return recorder.record(
        component=component,
        event=event,
        outcome=outcome,
        metadata=metadata,
    )
