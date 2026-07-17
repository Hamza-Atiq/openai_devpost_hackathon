from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from app.observability.context import current_correlation_id
from app.observability.recorder import observe


class AuditEventStore(Protocol):
    audit_events: dict[str, list[Mapping[str, Any]]]


def append_audit_event(
    state: AuditEventStore,
    workspace_id: str,
    *,
    event_type: str,
    summary: str,
    structured_payload: Mapping[str, Any] | None = None,
    actor_type: str = "organizer",
) -> None:
    event = {
        "id": str(uuid4()),
        "actor_type": actor_type,
        "event_type": event_type,
        "summary": summary,
        "structured_payload": dict(structured_payload or {}),
        "occurred_at": datetime.now(UTC).isoformat(),
        "agent_provenance": None,
        "correlation_id": current_correlation_id(),
    }
    state.audit_events.setdefault(workspace_id, []).append(event)
    observe(
        component="audit",
        event=event_type,
        outcome="recorded",
        metadata={"actor_type": actor_type, "workspace_id": workspace_id},
    )
