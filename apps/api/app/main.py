from fastapi import FastAPI

from app.session_probe import SessionProbeConfig, build_session_probe_router


def create_app(*, probe_config: SessionProbeConfig | None = None) -> FastAPI:
    application = FastAPI(title="CrickOps AI API")
    application.include_router(
        build_session_probe_router(probe_config or SessionProbeConfig.from_env())
    )

    @application.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
