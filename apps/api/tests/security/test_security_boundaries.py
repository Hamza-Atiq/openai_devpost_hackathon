from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.limits.public_demo import DemoLimits, PublicDemoProtection
from app.main import create_app
from app.session_probe import SessionProbeConfig
from fastapi.testclient import TestClient

ORIGIN = "https://crickops.example"
CSRF_COOKIE = "__Host-crickops_csrf"


def _application():
    return create_app(
        probe_config=SessionProbeConfig(
            environment="test",
            cookie_secret="s" * 32,
            allowed_origins=(ORIGIN,),
        ),
        csrf_required=True,
    )


def _client() -> TestClient:
    app = _application()
    return TestClient(app, base_url=ORIGIN)


def _create(client: TestClient, sample_id: str = "global-community-cup") -> dict[str, object]:
    response = client.post(
        "/api/v1/workspaces",
        headers={"Origin": ORIGIN},
        json={"sample_id": sample_id},
    )
    assert response.status_code == 201
    assert client.cookies.get(CSRF_COOKIE)
    return response.json()


def _csrf_headers(client: TestClient) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": client.cookies.get(CSRF_COOKIE) or ""}


def test_workspace_mutations_require_allowed_origin_and_double_submit_token() -> None:
    client = _client()
    workspace = _create(client)
    body = {
        "confirmation": True,
        "expected_revision": workspace["tournament"]["revision"],
        "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
    }

    missing = client.post(
        "/api/v1/constraints/confirm",
        headers={"Origin": ORIGIN},
        json=body,
    )
    attacker = client.post(
        "/api/v1/constraints/confirm",
        headers={
            "Origin": "https://attacker.example",
            "X-CSRF-Token": client.cookies.get(CSRF_COOKIE) or "",
        },
        json=body,
    )
    accepted = client.post(
        "/api/v1/constraints/confirm",
        headers=_csrf_headers(client),
        json=body,
    )

    assert missing.status_code == 403
    assert missing.json()["code"] == "csrf_validation_failed"
    assert attacker.status_code == 403
    assert attacker.json()["code"] == "origin_not_allowed"
    assert accepted.status_code == 200


def test_untrusted_origin_cannot_bootstrap_workspace() -> None:
    response = _client().post(
        "/api/v1/workspaces",
        headers={"Origin": "https://attacker.example"},
        json={"sample_id": None},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "origin_not_allowed"


def test_one_guest_cannot_read_or_mutate_another_guests_identifiers() -> None:
    app = _application()
    owner = TestClient(app, base_url=ORIGIN)
    intruder = TestClient(app, base_url=ORIGIN)
    owner_workspace = _create(owner)
    _create(intruder, "pakistan-community-cup")
    confirmed = owner.post(
        "/api/v1/constraints/confirm",
        headers=_csrf_headers(owner),
        json={
            "confirmation": True,
            "expected_revision": owner_workspace["tournament"]["revision"],
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )
    assert confirmed.status_code == 200
    generated = owner.post(
        "/api/v1/schedule-runs",
        headers={**_csrf_headers(owner), "Idempotency-Key": "security-generation"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    )
    run = owner.get(f"/api/v1/schedule-runs/{generated.json()['run_id']}").json()
    foreign_draft_id = run["draft_ids"][0]

    read = intruder.get(f"/api/v1/schedule-drafts/{foreign_draft_id}")
    approve = intruder.post(
        f"/api/v1/schedule-drafts/{foreign_draft_id}/approve",
        headers={**_csrf_headers(intruder), "Idempotency-Key": "foreign-approval"},
        json={"confirmation": True},
    )

    assert read.status_code == 404
    assert approve.status_code == 409
    assert owner.get(f"/api/v1/schedule-drafts/{foreign_draft_id}").status_code == 200


def test_export_recursively_redacts_internal_diagnostics_and_secrets() -> None:
    client = _client()
    _create(client)
    workspace = next(iter(client.app.state.workspace_store._items.values()))
    workspace.weather["provider_metadata"] = {
        "authorization": "Bearer should-not-export",
        "trace_id": "trace-should-not-export",
        "safe_quality": "complete",
    }
    workspace.weather["safe_quality"] = "complete"
    workspace.feedback.append(
        {
            "reason": "other",
            "hidden_reasoning": "never export this",
            "note": "Organizer-visible note",
        }
    )

    exported = client.get("/api/v1/workspace/export").text

    assert "should-not-export" not in exported
    assert "never export this" not in exported
    assert "Organizer-visible note" in exported
    assert "complete" in exported


def test_rate_limit_denial_reports_reset_and_preserves_workspace_state() -> None:
    now = datetime(2026, 7, 16, 12, tzinfo=UTC)
    protection = PublicDemoProtection(
        limits=DemoLimits(generation_requests_per_workspace_24h=0),
        clock=lambda: now,
        pseudonym_salt=b"security-evaluation-salt-value",
    )
    app = create_app(
        probe_config=SessionProbeConfig(
            environment="test",
            cookie_secret="s" * 32,
            allowed_origins=(ORIGIN,),
        ),
        demo_protection=protection,
        csrf_required=True,
    )
    client = TestClient(app, base_url=ORIGIN)
    workspace = _create(client)
    client.post(
        "/api/v1/constraints/confirm",
        headers=_csrf_headers(client),
        json={
            "confirmation": True,
            "expected_revision": workspace["tournament"]["revision"],
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )

    response = client.post(
        "/api/v1/schedule-runs",
        headers={**_csrf_headers(client), "Idempotency-Key": "limited-security-run"},
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    )
    stored = next(iter(app.state.workspace_store._items.values()))

    assert response.status_code == 429
    assert (now + timedelta(hours=24)).isoformat() in response.json()["detail"]
    assert stored.schedule_runs == {}
    assert stored.drafts == {}
