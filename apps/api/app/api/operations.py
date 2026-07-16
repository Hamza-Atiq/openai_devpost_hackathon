from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from app.agents.schemas import AgentMode
from app.api.problems import APIProblem
from app.api.routes import require_workspace
from app.api.workspace import GuestWorkspace
from app.observability.dependency_health import DependencyStatus

_SENSITIVE_KEY_PARTS = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "diagnostic",
        "hidden_reasoning",
        "idempotency",
        "password",
        "provider_metadata",
        "raw_prompt",
        "secret",
        "stack_trace",
        "token",
        "tool_call",
        "trace_id",
    }
)
_AUDIT_PUBLIC_FIELDS = (
    "id",
    "actor_type",
    "event_type",
    "summary",
    "structured_payload",
    "occurred_at",
    "agent_provenance",
)


@dataclass(slots=True)
class OperationsState:
    audit_events: dict[str, list[Mapping[str, Any]]] = field(default_factory=dict)
    dependency_status: dict[str, DependencyStatus] = field(
        default_factory=lambda: {
            "configuration": DependencyStatus.HEALTHY,
            "database": DependencyStatus.HEALTHY,
        }
    )
    critical_dependencies: frozenset[str] = frozenset({"configuration", "database"})
    mode: AgentMode = AgentMode.DETERMINISTIC
    provider: str | None = None
    model: str | None = None
    emergency_cached_results: bool = False


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return any(
        normalized == part or normalized.endswith(f"_{part}") for part in _SENSITIVE_KEY_PARTS
    )


def _organizer_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _organizer_safe(item)
            for key, item in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_organizer_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _audit_event_view(event: Mapping[str, Any]) -> dict[str, object]:
    return {
        field_name: _organizer_safe(event[field_name])
        for field_name in _AUDIT_PUBLIC_FIELDS
        if field_name in event
    }


def _event_value(event: Mapping[str, Any], name: str) -> str:
    return str(event.get(name, ""))


def _encode_cursor(
    *,
    workspace_id: str,
    offset: int,
    event_type: str | None,
    actor_type: str | None,
) -> str:
    payload = json.dumps(
        {
            "workspace_id": workspace_id,
            "offset": offset,
            "event_type": event_type,
            "actor_type": actor_type,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(
    cursor: str,
    *,
    workspace_id: str,
    event_type: str | None,
    actor_type: str | None,
) -> int:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if set(payload) != {"workspace_id", "offset", "event_type", "actor_type"}:
            raise ValueError("unexpected cursor fields")
        if (
            payload["workspace_id"] != workspace_id
            or payload["event_type"] != event_type
            or payload["actor_type"] != actor_type
            or not isinstance(payload["offset"], int)
            or payload["offset"] < 0
        ):
            raise ValueError("cursor does not match the current query")
        return payload["offset"]
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise APIProblem(
            status=422,
            code="invalid_audit_cursor",
            title="Invalid audit cursor",
            detail="The audit cursor is invalid or does not match the requested filters.",
        ) from error


def _workspace_export(
    workspace: GuestWorkspace,
    audit_events: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    tournament = workspace.tournament.model_dump(mode="json") if workspace.tournament else None
    organizer_workspace = {
        "workspace_id": workspace.workspace_id,
        "tournament": tournament,
        "weather": workspace.weather,
        "schedule_runs": workspace.schedule_runs,
        "drafts": workspace.drafts,
        "official_versions": workspace.official_versions,
        "edits": workspace.edits,
        "disruptions": workspace.disruptions,
        "schedule_diffs": workspace.schedule_diffs,
    }
    return {
        "schema_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "workspace": _organizer_safe(organizer_workspace),
        "audit_events": [_audit_event_view(event) for event in audit_events],
    }


def _mode_label(mode: AgentMode) -> str:
    return {
        AgentMode.GPT_5_6: "GPT-5.6 mode",
        AgentMode.FALLBACK_MODEL: "Fallback model mode",
        AgentMode.DETERMINISTIC: "Deterministic mode",
    }[mode]


def build_operations_router(state: OperationsState) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/workspace/export")
    def export_workspace(
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> JSONResponse:
        content = _workspace_export(
            workspace,
            state.audit_events.get(workspace.workspace_id, ()),
        )
        return JSONResponse(
            content=content,
            headers={
                "Content-Disposition": "attachment; filename=crickops-tournament.json",
                "X-CrickOps-Export-Mode": "synchronous",
            },
        )

    @router.get("/api/v1/audit-events")
    def audit_events(
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
        cursor: Annotated[str | None, Query(max_length=1024)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        event_type: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
        actor_type: Annotated[str | None, Query(min_length=1, max_length=40)] = None,
    ) -> dict[str, object]:
        filtered = [
            event
            for event in state.audit_events.get(workspace.workspace_id, ())
            if (event_type is None or _event_value(event, "event_type") == event_type)
            and (actor_type is None or _event_value(event, "actor_type") == actor_type)
        ]
        filtered.sort(key=lambda event: _event_value(event, "occurred_at"), reverse=True)
        offset = (
            0
            if cursor is None
            else _decode_cursor(
                cursor,
                workspace_id=workspace.workspace_id,
                event_type=event_type,
                actor_type=actor_type,
            )
        )
        if offset > len(filtered):
            raise APIProblem(
                status=422,
                code="invalid_audit_cursor",
                title="Invalid audit cursor",
                detail="The audit cursor points beyond the available event history.",
            )
        end = min(offset + limit, len(filtered))
        has_more = end < len(filtered)
        next_cursor = (
            _encode_cursor(
                workspace_id=workspace.workspace_id,
                offset=end,
                event_type=event_type,
                actor_type=actor_type,
            )
            if has_more
            else None
        )
        return {
            "items": [_audit_event_view(event) for event in filtered[offset:end]],
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    @router.get("/health/ready")
    def health_ready(response: Response) -> dict[str, object]:
        dependency_names = set(state.dependency_status) | set(state.critical_dependencies)
        components = []
        ready = True
        for name in sorted(dependency_names):
            dependency_status = state.dependency_status.get(name, DependencyStatus.UNAVAILABLE)
            critical = name in state.critical_dependencies
            if critical and dependency_status is not DependencyStatus.HEALTHY:
                ready = False
            components.append({"name": name, "status": dependency_status, "critical": critical})
        if not ready:
            response.status_code = 503
        return {"status": "ready" if ready else "not_ready", "components": components}

    @router.get("/api/v1/system/mode")
    def system_mode(
        _workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        conversational_available = state.mode is not AgentMode.DETERMINISTIC
        return {
            "mode": state.mode,
            "label": _mode_label(state.mode),
            "provider": state.provider if conversational_available else None,
            "model": state.model if conversational_available else None,
            "conversational_available": conversational_available,
            "deterministic_services_available": True,
            "fabricated_agent_response": False,
            "emergency_cached_results": state.emergency_cached_results,
        }

    return router
