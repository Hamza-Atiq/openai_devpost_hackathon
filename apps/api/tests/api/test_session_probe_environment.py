from app.main import create_app
from app.session_probe import SessionProbeConfig
from fastapi.testclient import TestClient


def test_session_probe_is_not_mounted_in_production() -> None:
    app = create_app(
        probe_config=SessionProbeConfig(
            environment="production",
            cookie_secret="test-secret",
            allowed_origins=("https://crickops.vercel.app",),
        )
    )

    response = TestClient(app).get("/api/v1/spike/session")

    assert response.status_code == 404
