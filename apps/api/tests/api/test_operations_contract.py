from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.agents.schemas import AgentMode
from app.api.operations import OperationsState, build_operations_router
from app.api.problems import install_problem_handlers
from app.api.routes import build_v1_router
from app.api.workspace import GuestWorkspaceStore
from app.observability.dependency_health import DependencyStatus
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _uuid7(value: int) -> str:
    return str(UUID(int=(7 << 76) | (2 << 62) | value))


def _application(
    *,
    dependencies: dict[str, DependencyStatus] | None = None,
    critical_dependencies: frozenset[str] = frozenset({"database", "configuration"}),
    mode: AgentMode = AgentMode.GPT_5_6,
) -> tuple[FastAPI, OperationsState]:
    app = FastAPI()
    install_problem_handlers(app)
    store = GuestWorkspaceStore()
    state = OperationsState(
        dependency_status=dependencies
        or {
            "database": DependencyStatus.HEALTHY,
            "configuration": DependencyStatus.HEALTHY,
            "openai": DependencyStatus.HEALTHY,
            "weather": DependencyStatus.HEALTHY,
        },
        critical_dependencies=critical_dependencies,
        mode=mode,
        provider="openai" if mode is AgentMode.GPT_5_6 else None,
        model="gpt-5.6-sol" if mode is AgentMode.GPT_5_6 else None,
    )
    app.state.workspace_store = store
    app.include_router(build_operations_router(state))
    app.include_router(build_v1_router(store))
    return app, state


def _guest(app: FastAPI) -> tuple[TestClient, str]:
    client = TestClient(app, base_url="https://testserver")
    created = client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    )
    assert created.status_code == 201
    return client, created.json()["workspace_id"]


def _event(index: int, workspace_id: str, *, event_type: str) -> dict[str, object]:
    return {
        "id": _uuid7(index + 10),
        "workspace_id": workspace_id,
        "tournament_id": _uuid7(index + 100),
        "actor_type": "organizer",
        "event_type": event_type,
        "summary": f"Organizer event {index}",
        "structured_payload": {
            "schedule_version": index,
            "raw_prompt": "must not leave the server",
            "nested": {"trace_id": "internal", "decision": "approved"},
        },
        "occurred_at": datetime(2026, 7, 16, 8, index, tzinfo=UTC).isoformat(),
        "stack_trace": "internal diagnostic",
    }


def test_export_is_synchronous_and_redacts_internal_fields() -> None:
    app, state = _application()
    client, workspace_id = _guest(app)
    workspace = next(iter(app.state.workspace_store._items.values()))
    workspace.schedule_runs["run-1"] = {
        "status": "ready",
        "profile": "balanced",
        "api_key": "secret",
        "provider_metadata": {"request_id": "private"},
    }
    state.audit_events[workspace_id] = [_event(1, workspace_id, event_type="schedule_approved")]

    response = client.get("/api/v1/workspace/export")

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["x-crickops-export-mode"] == "synchronous"
    document = response.json()
    assert document["workspace"]["workspace_id"] == workspace_id
    assert document["workspace"]["tournament"]["name"] == "Global Community Cricket Cup"
    assert document["workspace"]["schedule_runs"]["run-1"] == {
        "status": "ready",
        "profile": "balanced",
    }
    assert document["audit_events"][0]["structured_payload"] == {
        "schedule_version": 1,
        "nested": {"decision": "approved"},
    }
    serialized = response.text.lower()
    for forbidden in (
        "api_key",
        "raw_prompt",
        "provider_metadata",
        "stack_trace",
        "trace_id",
        "job_id",
        "status_url",
    ):
        assert forbidden not in serialized


def test_audit_events_are_paginated_with_an_opaque_cursor() -> None:
    app, state = _application()
    client, workspace_id = _guest(app)
    state.audit_events[workspace_id] = [
        _event(index, workspace_id, event_type="schedule_approved") for index in range(4)
    ]

    first = client.get("/api/v1/audit-events", params={"limit": 2})
    second = client.get(
        "/api/v1/audit-events",
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )

    assert first.status_code == 200
    assert [item["summary"] for item in first.json()["items"]] == [
        "Organizer event 3",
        "Organizer event 2",
    ]
    assert first.json()["has_more"] is True
    assert first.json()["next_cursor"]
    assert [item["summary"] for item in second.json()["items"]] == [
        "Organizer event 1",
        "Organizer event 0",
    ]
    assert second.json()["has_more"] is False
    assert second.json()["next_cursor"] is None


def test_audit_filters_are_bound_to_the_cursor() -> None:
    app, state = _application()
    client, workspace_id = _guest(app)
    state.audit_events[workspace_id] = [
        _event(1, workspace_id, event_type="schedule_approved"),
        _event(2, workspace_id, event_type="schedule_rejected"),
        _event(3, workspace_id, event_type="schedule_approved"),
    ]

    first = client.get(
        "/api/v1/audit-events",
        params={"limit": 1, "event_type": "schedule_approved"},
    )
    invalid = client.get(
        "/api/v1/audit-events",
        params={
            "limit": 1,
            "event_type": "schedule_rejected",
            "cursor": first.json()["next_cursor"],
        },
    )

    assert first.json()["items"][0]["event_type"] == "schedule_approved"
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_audit_cursor"


def test_audit_and_mode_require_the_guest_workspace() -> None:
    app, _state = _application()
    client = TestClient(app, base_url="https://testserver")

    audit = client.get("/api/v1/audit-events")
    mode = client.get("/api/v1/system/mode")

    assert audit.status_code == 401
    assert mode.status_code == 401


def test_readiness_stays_ready_when_only_optional_providers_are_degraded() -> None:
    app, _state = _application(
        dependencies={
            "database": DependencyStatus.HEALTHY,
            "configuration": DependencyStatus.HEALTHY,
            "openai": DependencyStatus.UNAVAILABLE,
            "weather": DependencyStatus.DEGRADED,
        }
    )
    response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "components": [
            {"name": "configuration", "status": "healthy", "critical": True},
            {"name": "database", "status": "healthy", "critical": True},
            {"name": "openai", "status": "unavailable", "critical": False},
            {"name": "weather", "status": "degraded", "critical": False},
        ],
    }
    assert "detail" not in response.text
    assert "circuit" not in response.text


def test_readiness_returns_503_when_a_critical_component_is_unavailable() -> None:
    app, _state = _application(
        dependencies={
            "database": DependencyStatus.UNAVAILABLE,
            "configuration": DependencyStatus.HEALTHY,
            "openai": DependencyStatus.HEALTHY,
        }
    )

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["components"][1] == {
        "name": "database",
        "status": "unavailable",
        "critical": True,
    }


def test_system_mode_exposes_capability_without_fabricating_agent_output() -> None:
    app, state = _application(mode=AgentMode.DETERMINISTIC)
    client, _workspace_id = _guest(app)
    state.emergency_cached_results = True

    response = client.get("/api/v1/system/mode")

    assert response.status_code == 200
    assert response.json() == {
        "mode": "deterministic",
        "label": "Deterministic mode",
        "provider": None,
        "model": None,
        "conversational_available": False,
        "deterministic_services_available": True,
        "fabricated_agent_response": False,
        "emergency_cached_results": True,
    }


def test_operations_openapi_has_no_export_job_resource() -> None:
    app, _state = _application()
    paths = app.openapi()["paths"]

    assert "/api/v1/workspace/export" in paths
    assert "/api/v1/audit-events" in paths
    assert "/api/v1/system/mode" in paths
    assert "/health/ready" in paths
    assert all("export-job" not in path for path in paths)
