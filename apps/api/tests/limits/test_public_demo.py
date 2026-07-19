from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.limits.public_demo import (
    BudgetMode,
    DemoLimits,
    PublicDemoProtection,
    UsageAction,
)
from app.main import create_app
from app.settings import ServerSettings
from fastapi.testclient import TestClient

NOW = datetime(2026, 7, 16, 12, tzinfo=UTC)


def _protection(**overrides: object) -> tuple[PublicDemoProtection, list[datetime]]:
    clock = [NOW]
    limits = DemoLimits(**overrides)
    return (
        PublicDemoProtection(limits=limits, clock=lambda: clock[0], pseudonym_salt=b"s" * 32),
        clock,
    )


def test_defaults_match_the_approved_public_demo_limits() -> None:
    assert DemoLimits() == DemoLimits(
        active_jobs_per_workspace=1,
        generation_requests_per_workspace_24h=12,
        repair_requests_per_workspace_24h=12,
        agent_calls_per_workspace_24h=80,
        agent_calls_per_ip_24h=300,
        weather_refreshes_per_workspace_24h=60,
        concurrent_solver_jobs_per_worker=4,
        queued_jobs_per_workspace=1,
        provider_daily_budget_usd=50,
    )


@pytest.mark.parametrize(
    ("action", "limit_name", "count"),
    [
        (UsageAction.GENERATION, "generation_requests_per_workspace_24h", 12),
        (UsageAction.REPAIR, "repair_requests_per_workspace_24h", 12),
        (UsageAction.AGENT, "agent_calls_per_workspace_24h", 80),
        (UsageAction.WEATHER, "weather_refreshes_per_workspace_24h", 60),
    ],
)
def test_workspace_rolling_limits_return_reset_time_and_preserve_future_capacity(
    action: UsageAction,
    limit_name: str,
    count: int,
) -> None:
    protection, clock = _protection()
    for _ in range(count):
        assert protection.consume(
            action, workspace_id="workspace-1", ip_address="203.0.113.4"
        ).allowed

    denied = protection.consume(action, workspace_id="workspace-1", ip_address="203.0.113.4")
    assert denied.allowed is False
    assert denied.limit_name == limit_name
    assert denied.reset_at == NOW + timedelta(hours=24)

    clock[0] += timedelta(hours=24, microseconds=1)
    assert protection.consume(action, workspace_id="workspace-1", ip_address="203.0.113.4").allowed


def test_agent_ip_limit_applies_across_isolated_workspaces() -> None:
    protection, _clock = _protection(agent_calls_per_workspace_24h=400)
    for index in range(300):
        decision = protection.consume(
            UsageAction.AGENT,
            workspace_id=f"workspace-{index}",
            ip_address="203.0.113.9",
        )
        assert decision.allowed

    denied = protection.consume(
        UsageAction.AGENT,
        workspace_id="workspace-over-limit",
        ip_address="203.0.113.9",
    )
    assert denied.allowed is False
    assert denied.limit_name == "agent_calls_per_ip_24h"


def test_budget_conserves_at_75_percent_and_forces_deterministic_at_100_percent() -> None:
    protection, _clock = _protection(provider_daily_budget_usd=50)

    protection.record_provider_cost(37.50)
    assert protection.budget_mode is BudgetMode.CONSERVE
    assert protection.nonessential_retries_allowed is False
    assert protection.agent_work_allowed is True

    protection.record_provider_cost(12.50)
    assert protection.budget_mode is BudgetMode.DETERMINISTIC
    assert protection.agent_work_allowed is False

    protection.reset_daily_budget()
    assert protection.budget_mode is BudgetMode.NORMAL
    protection.set_emergency_deterministic(True)
    assert protection.budget_mode is BudgetMode.DETERMINISTIC
    assert protection.agent_work_allowed is False


def test_concurrency_and_abuse_records_are_bounded_and_pseudonymous() -> None:
    protection, _clock = _protection(concurrent_solver_jobs_per_worker=2)
    first = protection.acquire_job("workspace-1")
    second = protection.acquire_job("workspace-2")
    same_workspace = protection.acquire_job("workspace-1")
    worker_full = protection.acquire_job("workspace-3")

    assert first.allowed and second.allowed
    assert same_workspace.allowed is False
    assert same_workspace.limit_name == "active_jobs_per_workspace"
    assert worker_full.allowed is False
    assert worker_full.limit_name == "concurrent_solver_jobs_per_worker"
    protection.release_job("workspace-1")
    assert protection.acquire_job("workspace-3").allowed

    abuse = protection.abuse_records
    assert abuse
    assert abuse[0].workspace_pseudonym != "workspace-1"
    assert abuse[0].ip_pseudonym is None
    serialized = str(abuse).lower()
    assert "raw_prompt" not in serialized
    assert "workspace-1" not in serialized
    assert abuse[0].counter_value == 1
    assert abuse[0].limit_value == 1


def test_one_queued_job_per_workspace_is_reserved_and_released() -> None:
    protection, _clock = _protection(queued_jobs_per_workspace=1)

    assert protection.enqueue_job("workspace-1").allowed
    denied = protection.enqueue_job("workspace-1")
    assert denied.allowed is False
    assert denied.limit_name == "queued_jobs_per_workspace"

    protection.dequeue_job("workspace-1")
    assert protection.enqueue_job("workspace-1").allowed


def test_generation_limit_returns_reset_time_without_mutating_workspace() -> None:
    protection, _clock = _protection(generation_requests_per_workspace_24h=0)
    app = create_app(demo_protection=protection)
    client = TestClient(app, base_url="https://testserver")
    client.post("/api/v1/workspaces", json={"sample_id": "global-community-cup"})
    workspace = next(iter(app.state.workspace_store._items.values()))
    client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": workspace.tournament.revision,
            "selection": {
                "match_format_preset": "T20",
                "allocation_minutes": 240,
            },
        },
    )

    response = client.post(
        "/api/v1/schedule-runs",
        headers={"Idempotency-Key": "limited-generation"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    )

    assert response.status_code == 429
    assert response.json()["code"] == "public_demo_limit_exceeded"
    assert (NOW + timedelta(hours=24)).isoformat() in response.json()["detail"]
    assert workspace.schedule_runs == {}
    assert workspace.drafts == {}


def test_weather_limit_preserves_last_snapshot() -> None:
    protection, _clock = _protection(weather_refreshes_per_workspace_24h=0)
    app = create_app(demo_protection=protection)
    client = TestClient(app, base_url="https://testserver")
    client.post("/api/v1/workspaces", json={"sample_id": "global-community-cup"})
    before = client.get("/api/v1/weather").json()

    response = client.post("/api/v1/weather/refresh", json={"mode": "live"})

    assert response.status_code == 429
    assert client.get("/api/v1/weather").json() == before


def test_runtime_settings_activate_operator_deterministic_switch() -> None:
    settings = ServerSettings.from_env(
        {
            "CRICKOPS_ENV": "test",
            "CRICKOPS_PROVIDER_DAILY_BUDGET_USD": "75",
            "CRICKOPS_EMERGENCY_DETERMINISTIC_MODE": "true",
        }
    )

    app = create_app(server_settings=settings)

    assert app.state.demo_protection.limits.provider_daily_budget_usd == 75
    assert app.state.demo_protection.budget_mode is BudgetMode.DETERMINISTIC
