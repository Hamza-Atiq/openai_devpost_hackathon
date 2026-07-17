from fastapi import FastAPI, Request

from app.agents.schemas import AgentMode
from app.api.operations import OperationsState, build_operations_router
from app.api.problems import install_problem_handlers
from app.api.routes import build_v1_router
from app.api.schedules import build_schedule_router
from app.api.workspace import GuestWorkspaceStore
from app.session_probe import SessionProbeConfig, build_session_probe_router


def create_app(*, probe_config: SessionProbeConfig | None = None) -> FastAPI:
    application = FastAPI(title="CrickOps AI API")
    install_problem_handlers(application)
    application.state.workspace_store = GuestWorkspaceStore()
    application.state.operations = OperationsState(mode=AgentMode.DETERMINISTIC)
    application.include_router(build_v1_router(application.state.workspace_store))
    application.include_router(build_schedule_router(application.state.operations))
    application.include_router(build_operations_router(application.state.operations))
    application.include_router(
        build_session_probe_router(probe_config or SessionProbeConfig.from_env())
    )

    @application.middleware("http")
    async def private_workspace_cache_control(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/v1") and request.url.path != "/api/v1/samples":
            response.headers["Cache-Control"] = "private, no-store, max-age=0"
            response.headers["Vary"] = "Cookie"
        return response

    @application.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
