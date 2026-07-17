import os
from secrets import token_bytes

from agents.tracing import add_trace_processor
from fastapi import FastAPI, Request

from app.agents.schemas import AgentMode
from app.api.operations import OperationsState, build_operations_router
from app.api.problems import install_problem_handlers
from app.api.routes import COOKIE_NAME, build_v1_router
from app.api.schedules import build_schedule_router
from app.api.workspace import GuestWorkspaceStore, PostgresGuestWorkspaceStore
from app.deployment.runtime import database_engine
from app.limits.public_demo import DemoLimits, PublicDemoProtection
from app.observability.middleware import install_observability_middleware
from app.observability.recorder import ObservabilityRecorder
from app.observability.trace_processor import MinimalLocalTraceProcessor
from app.session_probe import SessionProbeConfig, build_session_probe_router
from app.settings import ServerSettings


def create_app(
    *,
    probe_config: SessionProbeConfig | None = None,
    install_sdk_tracing: bool = False,
    demo_protection: PublicDemoProtection | None = None,
    server_settings: ServerSettings | None = None,
    csrf_required: bool | None = None,
) -> FastAPI:
    application = FastAPI(title="CrickOps AI API")
    runtime_probe_config = probe_config or SessionProbeConfig.from_env()
    application.state.allowed_origins = frozenset(runtime_probe_config.allowed_origins)
    application.state.csrf_required = (
        csrf_required
        if csrf_required is not None
        else bool(
            server_settings and server_settings.environment.value in {"preview", "production"}
        )
    )
    application.state.observability = ObservabilityRecorder()
    if install_sdk_tracing:
        application.state.sdk_trace_processor = MinimalLocalTraceProcessor(
            application.state.observability
        )
        add_trace_processor(application.state.sdk_trace_processor)
    install_observability_middleware(application, application.state.observability)
    install_problem_handlers(application)
    if server_settings and server_settings.database_url:
        application.state.database_engine = database_engine(server_settings.database_url)
        application.state.workspace_store = PostgresGuestWorkspaceStore(
            application.state.database_engine
        )
    else:
        application.state.database_engine = None
        application.state.workspace_store = GuestWorkspaceStore()
    if demo_protection is None:
        demo_protection = PublicDemoProtection(
            limits=DemoLimits(
                provider_daily_budget_usd=(
                    server_settings.provider_daily_budget_usd if server_settings else 50
                )
            ),
            pseudonym_salt=token_bytes(32),
        )
        if server_settings and server_settings.emergency_deterministic_mode:
            demo_protection.set_emergency_deterministic(True)
    application.state.demo_protection = demo_protection
    application.state.operations = OperationsState(mode=AgentMode.DETERMINISTIC)
    application.include_router(
        build_v1_router(
            application.state.workspace_store,
            application.state.operations,
            application.state.demo_protection,
        )
    )
    application.include_router(
        build_schedule_router(application.state.operations, application.state.demo_protection)
    )
    application.include_router(build_operations_router(application.state.operations))
    application.include_router(build_session_probe_router(runtime_probe_config))

    @application.middleware("http")
    async def private_workspace_cache_control(request: Request, call_next):
        guest_token = request.cookies.get(COOKIE_NAME)
        if guest_token:
            restored = application.state.workspace_store.get(guest_token)
            if restored is not None and restored.audit_events:
                application.state.operations.audit_events[restored.workspace_id] = list(
                    restored.audit_events
                )
        response = await call_next(request)
        if guest_token:
            cached = application.state.workspace_store.cached(guest_token)
            if cached is not None:
                cached.audit_events = list(
                    application.state.operations.audit_events.get(cached.workspace_id, ())
                )
            application.state.workspace_store.persist(guest_token)
        if request.url.path.startswith("/api/v1") and request.url.path != "/api/v1/samples":
            response.headers["Cache-Control"] = "private, no-store, max-age=0"
            response.headers["Vary"] = "Cookie"
        return response

    @application.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    return application


_configured_settings = (
    ServerSettings.from_env() if os.environ.get("CRICKOPS_ENV") is not None else None
)
app = create_app(install_sdk_tracing=True, server_settings=_configured_settings)
