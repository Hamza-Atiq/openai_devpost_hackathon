from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request, Response, status
from pydantic import Field

from app.api.audit import append_audit_event
from app.api.problems import APIProblem
from app.api.setup_models import (
    TournamentSetupDraftInput,
    setup_state_from_input,
    setup_view,
)
from app.api.workspace import GuestWorkspace, GuestWorkspaceStore
from app.domain.common import DomainModel
from app.domain.samples import available_samples, load_sample
from app.limits.public_demo import PublicDemoProtection, UsageAction
from app.security.csrf import (
    CSRF_COOKIE_NAME,
    validate_bootstrap_origin,
    validate_workspace_mutation,
)
from app.weather.service import WeatherServiceProtocol

if TYPE_CHECKING:
    from app.api.operations import OperationsState

COOKIE_NAME = "__Host-crickops_guest"


class CreateWorkspaceInput(DomainModel):
    sample_id: str | None = Field(default=None, max_length=80)


class ConfirmationInput(DomainModel):
    confirmation: bool


class ConfirmConstraintsInput(DomainModel):
    confirmation: bool
    expected_revision: int = Field(ge=0)
    selection: Mapping[str, Any]


class WeatherRefreshInput(DomainModel):
    mode: Literal["live", "deterministic"] = "live"
    venue_ids: tuple[str, ...] = ()


class WeatherThresholdInput(DomainModel):
    metric: Literal[
        "precipitation_probability",
        "temperature_max_c",
        "temperature_min_c",
        "wind_speed_kmh",
    ]
    value: float


class GenericPayload(DomainModel):
    payload: Mapping[str, Any] = {}


class PrecheckInput(DomainModel):
    expected_revision: int = Field(ge=0)


def _load_requested_sample(sample_id: str | None):
    if sample_id is None:
        return None
    try:
        return load_sample(sample_id)
    except ValueError as error:
        raise APIProblem(
            status=422,
            code="invalid_sample",
            title="Invalid sample tournament",
            detail=str(error),
        ) from error


def _workspace_view(workspace: GuestWorkspace) -> dict[str, object]:
    return {
        "workspace_id": workspace.workspace_id,
        "tournament": (
            setup_view(workspace.tournament, workspace.setup_draft).model_dump(mode="json")
            if workspace.tournament
            else None
        ),
        "weather": workspace.weather,
        "constraint_confirmation": workspace.constraint_confirmation,
    }


def require_workspace(
    request: Request,
    guest_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> GuestWorkspace:
    workspace = request.app.state.workspace_store.get(guest_token)
    if workspace is None:
        raise APIProblem(
            status=401,
            code="workspace_auth_required",
            title="Guest workspace required",
            detail="Create or restore a guest workspace before using this route.",
        )
    validate_workspace_mutation(request, workspace.csrf_token)
    return workspace


def build_v1_router(
    store: GuestWorkspaceStore,
    operations: OperationsState | None = None,
    demo_protection: PublicDemoProtection | None = None,
    weather_service: WeatherServiceProtocol | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def sample_weather(workspace: GuestWorkspace) -> dict[str, object]:
        if workspace.tournament is None or weather_service is None:
            return {
                "mode": "live",
                "quality": "not_requested",
                "demo_mode_available": True,
                "scenario_id": None,
            }
        try:
            return weather_service.refresh(
                workspace.tournament,
                mode="deterministic",
                scenario_id="sample-baseline-v1",
            )
        except Exception:
            return {
                "mode": "deterministic",
                "quality": "unavailable",
                "demo_mode_available": True,
                "scenario_id": "sample-baseline-v1",
                "provider": None,
                "coverage": 0.0,
                "slot_risks": {},
                "slot_details": {},
                "guidance": "Weather risk is unavailable; deterministic scheduling remains usable.",
            }

    def clear_tournament_state(workspace: GuestWorkspace) -> None:
        workspace.schedule_runs.clear()
        workspace.drafts.clear()
        workspace.draft_revisions.clear()
        workspace.rejected_drafts.clear()
        workspace.idempotency.clear()
        workspace.official_versions.clear()
        workspace.edits.clear()
        workspace.disruptions.clear()
        workspace.schedule_diffs.clear()
        workspace.feedback.clear()
        workspace.constraint_confirmation = None
        workspace.setup_draft = None
        workspace.audit_events.clear()
        if operations is not None:
            operations.audit_events[workspace.workspace_id] = []

    @router.get("/samples")
    def list_samples() -> list[dict[str, object]]:
        return [
            {
                "sample_id": sample_id,
                "name": load_sample(sample_id).name,
                "match_format_preset": "T20",
            }
            for sample_id in available_samples()
        ]

    @router.post("/workspaces", status_code=status.HTTP_201_CREATED)
    def create_workspace(
        body: CreateWorkspaceInput,
        request: Request,
        response: Response,
    ) -> dict[str, object]:
        validate_bootstrap_origin(request)
        token, workspace = store.create(_load_requested_sample(body.sample_id))
        workspace.weather = sample_weather(workspace)
        response.set_cookie(
            COOKIE_NAME,
            token,
            secure=True,
            httponly=True,
            samesite="lax",
            path="/",
        )
        response.set_cookie(
            CSRF_COOKIE_NAME,
            workspace.csrf_token,
            secure=True,
            httponly=False,
            samesite="strict",
            path="/",
        )
        return _workspace_view(workspace)

    @router.get("/workspace")
    def read_workspace(workspace: Annotated[GuestWorkspace, Depends(require_workspace)]):
        return _workspace_view(workspace)

    @router.delete("/workspace", status_code=status.HTTP_202_ACCEPTED)
    def delete_workspace(
        body: ConfirmationInput,
        response: Response,
        guest_token: Annotated[str, Cookie(alias=COOKIE_NAME)],
        _workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, str]:
        if not body.confirmation:
            raise APIProblem(
                status=422,
                code="confirmation_required",
                title="Confirmation required",
                detail="Workspace deletion requires explicit confirmation.",
            )
        store.delete(guest_token)
        response.delete_cookie(COOKIE_NAME, secure=True, httponly=True, path="/")
        response.delete_cookie(CSRF_COOKIE_NAME, secure=True, httponly=False, path="/")
        return {"status": "deletion_accepted"}

    @router.post("/workspace/reset")
    def reset_workspace(
        body: CreateWorkspaceInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        clear_tournament_state(workspace)
        workspace.tournament = _load_requested_sample(body.sample_id)
        workspace.weather = sample_weather(workspace)
        if operations is not None:
            append_audit_event(
                operations,
                workspace.workspace_id,
                event_type="workspace_reset",
                summary=(
                    "Demo workspace reset to the selected sample."
                    if workspace.tournament is not None
                    else "Demo workspace reset to a blank tournament."
                ),
                structured_payload={"sample_id": body.sample_id},
            )
        return _workspace_view(workspace)

    @router.get("/tournament")
    def read_tournament(
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        if workspace.tournament is None:
            raise APIProblem(
                status=404,
                code="tournament_not_found",
                title="No active tournament",
                detail="Create a blank tournament or load a sample first.",
            )
        return setup_view(workspace.tournament, workspace.setup_draft)

    @router.put("/tournament")
    def replace_tournament(
        body: TournamentSetupDraftInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
    ):
        replay = workspace.idempotency.get(f"setup:{idempotency_key}")
        if replay is not None:
            return replay
        if workspace.tournament is None:
            raise APIProblem(
                status=409,
                code="tournament_not_found",
                title="No active tournament",
                detail="Create or load a tournament before editing setup.",
            )
        if body.expected_revision != workspace.tournament.revision:
            raise APIProblem(
                status=409,
                code="stale_tournament_revision",
                title="Tournament revision is stale",
                detail="Reload the latest saved setup before applying these changes.",
                retryable=True,
            )
        window_days = (body.end_date - body.start_date).days + 1
        if not 7 <= window_days <= 21:
            raise APIProblem(
                status=422,
                code="invalid_tournament_window",
                title="Tournament window is invalid",
                detail="Choose a tournament window between 7 and 21 calendar days inclusive.",
            )
        if any(day < body.start_date or day > body.end_date for day in body.blackout_dates):
            raise APIProblem(
                status=422,
                code="invalid_blackout_date",
                title="Blackout date is outside the tournament",
                detail="Every blackout date must fall inside the tournament window.",
            )
        if len({venue.iana_time_zone for venue in body.venues}) != 1:
            raise APIProblem(
                status=422,
                code="venue_timezone_mismatch",
                title="Venue timezones do not match",
                detail="Version 1 requires both venues to use the same IANA timezone.",
            )
        from app.scheduling.slot_patterns import expand_slot_patterns

        workspace.tournament = expand_slot_patterns(
            workspace.tournament,
            body,
            now=datetime.now(UTC),
        )
        workspace.setup_draft = setup_state_from_input(body)
        workspace.constraint_confirmation = None
        result = setup_view(workspace.tournament, workspace.setup_draft).model_dump(mode="json")
        workspace.idempotency[f"setup:{idempotency_key}"] = result
        if operations is not None:
            append_audit_event(
                operations,
                workspace.workspace_id,
                event_type="tournament_setup_saved",
                summary="Organizer saved tournament setup changes.",
                structured_payload={
                    "revision": workspace.tournament.revision,
                    "slot_count": len(workspace.tournament.slots),
                },
            )
        return result

    @router.patch("/tournament")
    def patch_tournament(
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        if workspace.tournament is None:
            raise APIProblem(
                status=404,
                code="tournament_not_found",
                title="No active tournament",
                detail="Create a tournament before editing it.",
            )
        from app.domain.tournament import TournamentConfig

        current = workspace.tournament.model_dump(mode="python")
        workspace.tournament = TournamentConfig.model_validate(
            {**current, **body, "revision": workspace.tournament.revision + 1}
        )
        return workspace.tournament

    @router.get("/locations/search")
    def search_locations(
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
        query: Annotated[str, Query(min_length=2, max_length=120)],
        language: Annotated[str | None, Query(max_length=12)] = None,
    ) -> list[object]:
        del workspace, query, language
        return []

    @router.post("/venues/{venue_id}/confirm-location")
    def confirm_location(
        venue_id: str,
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        del body
        venues = workspace.tournament.venues if workspace.tournament else ()
        venue = next((item for item in venues if str(item.id) == venue_id), None)
        if venue is None:
            raise APIProblem(
                status=404,
                code="venue_not_found",
                title="Venue not found",
                detail="The venue does not belong to this workspace tournament.",
            )
        return venue.model_dump(mode="json")

    @router.post("/tournament/interpret")
    def interpret_tournament(
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        del body, workspace
        return {"status": "clarification_required", "proposals": []}

    @router.post("/constraints/propose")
    def propose_constraint(
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        del workspace
        return {"status": "proposed", "proposal": body}

    @router.post("/constraints/confirm")
    def confirm_constraints(
        body: ConfirmConstraintsInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        if workspace.tournament is None:
            raise APIProblem(
                status=409,
                code="tournament_not_ready",
                title="Tournament is not ready",
                detail="Create or load a tournament before confirming constraints.",
            )
        if not body.confirmation:
            raise APIProblem(
                status=422,
                code="confirmation_required",
                title="Confirmation required",
                detail="Review and explicitly confirm the hard constraints.",
            )
        if body.expected_revision != workspace.tournament.revision:
            raise APIProblem(
                status=409,
                code="stale_tournament_revision",
                title="Tournament revision is stale",
                detail="Reload the latest setup before confirming constraints.",
                retryable=True,
            )

        from app.domain.tournament import TournamentStatus

        next_revision = workspace.tournament.revision + 1
        workspace.tournament = workspace.tournament.model_copy(
            update={"status": TournamentStatus.READY_TO_SCHEDULE, "revision": next_revision}
        )
        previous_selection = (
            dict(workspace.constraint_confirmation.get("selection", {}))
            if workspace.constraint_confirmation is not None
            else {}
        )
        previous_selection.update(body.selection)
        workspace.constraint_confirmation = {
            "selection": previous_selection,
            "confirmed_revision": next_revision,
        }
        if operations is not None:
            append_audit_event(
                operations,
                workspace.workspace_id,
                event_type="constraints_confirmed",
                summary="Organizer confirmed structured tournament constraints.",
                structured_payload={
                    "revision": next_revision,
                    "selection_keys": sorted(previous_selection),
                },
            )
        return {
            "status": TournamentStatus.READY_TO_SCHEDULE,
            "revision": next_revision,
            "selection": previous_selection,
        }

    @router.post("/constraints/reject")
    def reject_constraints(
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        del workspace
        return {"status": "rejected", "selection": body}

    @router.post("/tournament/precheck")
    def precheck_tournament(
        body: PrecheckInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        from app.api.readiness import run_workspace_precheck
        from app.domain.tournament import TournamentStatus

        if workspace.tournament is None:
            raise APIProblem(
                status=409,
                code="tournament_not_ready",
                title="Tournament is not ready",
                detail="Create or load a tournament before checking readiness.",
            )
        if body.expected_revision != workspace.tournament.revision:
            raise APIProblem(
                status=409,
                code="stale_tournament_revision",
                title="Tournament revision is stale",
                detail="Reload the latest setup before checking readiness.",
                retryable=True,
            )
        confirmed_revision = (
            workspace.constraint_confirmation.get("confirmed_revision")
            if workspace.constraint_confirmation
            else None
        )
        confirmed = (
            workspace.tournament.status is TournamentStatus.READY_TO_SCHEDULE
            and confirmed_revision == workspace.tournament.revision
        )
        if not confirmed:
            return {
                "ready": False,
                "revision": workspace.tournament.revision,
                "violations": ["constraints_not_confirmed"],
                "evidence": [],
                "remedies": [],
            }
        result = run_workspace_precheck(workspace)
        return {
            "ready": result.can_solve,
            "revision": workspace.tournament.revision,
            "violations": [item.code for item in result.evidence],
            "evidence": [item.model_dump(mode="json") for item in result.evidence],
            "remedies": [item.model_dump(mode="json") for item in result.remedies],
        }

    @router.post("/weather/refresh")
    def refresh_weather(
        body: WeatherRefreshInput,
        request: Request,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        if demo_protection is not None:
            decision = demo_protection.consume(
                UsageAction.WEATHER,
                workspace_id=workspace.workspace_id,
                ip_address=request.client.host if request.client else None,
            )
            if not decision.allowed:
                reset = decision.reset_at.isoformat() if decision.reset_at else "capacity clears"
                raise APIProblem(
                    status=429,
                    code="public_demo_limit_exceeded",
                    title="Public demo limit reached",
                    detail=f"Weather refresh is temporarily limited; retry after {reset}.",
                    retryable=True,
                )
        if workspace.tournament is None:
            raise APIProblem(
                status=409,
                code="tournament_not_ready",
                title="Tournament is not ready",
                detail="Load or create a tournament before refreshing weather.",
            )
        workspace.weather = (
            weather_service.refresh(workspace.tournament, mode=body.mode)
            if weather_service is not None
            else {
                "mode": body.mode,
                "quality": "unavailable" if body.mode == "live" else "deterministic",
                "demo_mode_available": True,
                "scenario_id": None,
                "guidance": "Weather risk is planning guidance only.",
            }
        )
        return workspace.weather

    @router.get("/weather")
    def read_weather(
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        return workspace.weather

    @router.post("/weather/demo-scenarios/{scenario_id}/activate")
    def activate_demo_scenario(
        scenario_id: str,
        body: ConfirmationInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        if scenario_id != "rain-threshold-v1" or not body.confirmation:
            raise APIProblem(
                status=422,
                code="invalid_demo_scenario",
                title="Invalid demo scenario",
                detail="Select the supported scenario and confirm activation.",
            )
        if workspace.tournament is None:
            raise APIProblem(
                status=409,
                code="tournament_not_ready",
                title="Tournament is not ready",
                detail="Load or create a tournament before activating demo weather.",
            )
        workspace.weather = (
            weather_service.refresh(
                workspace.tournament,
                mode="deterministic",
                scenario_id=scenario_id,
            )
            if weather_service is not None
            else {
                "mode": "deterministic",
                "quality": "complete",
                "demo_mode_available": True,
                "scenario_id": scenario_id,
                "guidance": "Weather risk is planning guidance only.",
            }
        )
        return workspace.weather

    @router.post("/weather/thresholds")
    def propose_weather_threshold(
        body: WeatherThresholdInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        if body.metric == "precipitation_probability" and not 0 <= body.value <= 100:
            raise APIProblem(
                status=422,
                code="invalid_weather_threshold",
                title="Invalid weather threshold",
                detail="Precipitation probability must be between 0 and 100.",
            )
        proposal = body.model_dump(exclude={"schema_version"})
        workspace.weather["threshold_proposal"] = proposal
        return {"status": "proposed", "classification": "hard", "threshold": proposal}

    return router
