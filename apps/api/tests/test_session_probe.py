from __future__ import annotations

from app.main import create_app
from app.session_probe import COOKIE_NAME, SessionProbeConfig
from fastapi.testclient import TestClient

ORIGIN = "https://crickops.example"
SECRET = "task-005-cookie-secret-value-0001"


def make_client(*, environment: str = "production") -> TestClient:
    app = create_app(
        probe_config=SessionProbeConfig(
            environment=environment,
            cookie_secret=SECRET,
            allowed_origins=(ORIGIN,),
        )
    )
    return TestClient(app, base_url=ORIGIN)


def test_session_cookie_is_host_only_secure_and_private() -> None:
    with make_client() as client:
        response = client.get("/api/v1/spike/session")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store, max-age=0"
    assert response.headers["vary"] == "Cookie"
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{COOKIE_NAME}=")
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie
    assert "Domain=" not in set_cookie


def test_cookie_continuity_and_guest_isolation() -> None:
    with make_client() as first, make_client() as second:
        first_initial = first.get("/api/v1/spike/session").json()
        first_repeat = first.get("/api/v1/spike/session").json()
        second_initial = second.get("/api/v1/spike/session").json()

    assert first_repeat["session_id"] == first_initial["session_id"]
    assert second_initial["session_id"] != first_initial["session_id"]
    assert "session_token" not in first_initial


def test_mutation_requires_allowed_origin_and_matching_csrf_token() -> None:
    with make_client() as client:
        session = client.get("/api/v1/spike/session").json()

        missing = client.post("/api/v1/spike/session/mutations", json={"value": "one"})
        wrong_origin = client.post(
            "/api/v1/spike/session/mutations",
            json={"value": "one"},
            headers={"Origin": "https://attacker.example", "X-CSRF-Token": session["csrf_token"]},
        )
        accepted = client.post(
            "/api/v1/spike/session/mutations",
            json={"value": "one"},
            headers={"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]},
        )

    assert missing.status_code == 403
    assert wrong_origin.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["mutation_count"] == 1
    assert accepted.headers["cache-control"] == "private, no-store, max-age=0"


def test_production_cookie_is_rejected_by_preview_environment() -> None:
    with make_client(environment="production") as production:
        production.get("/api/v1/spike/session")
        production_cookie = production.cookies.get(COOKIE_NAME)

    with make_client(environment="preview") as preview:
        response = preview.get(
            "/api/v1/spike/session",
            headers={"Cookie": f"{COOKIE_NAME}={production_cookie}"},
        )

    assert response.status_code == 200
    assert response.json()["environment"] == "preview"
    assert response.headers["set-cookie"].split("=", 1)[1].split(";", 1)[0] != production_cookie


def test_probe_rejects_unknown_mutation_fields() -> None:
    with make_client() as client:
        session = client.get("/api/v1/spike/session").json()
        response = client.post(
            "/api/v1/spike/session/mutations",
            json={"value": "one", "workspace_id": "guessed"},
            headers={"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]},
        )

    assert response.status_code == 422
