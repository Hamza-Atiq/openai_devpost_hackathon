from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import Field

from app.api.problems import APIProblem
from app.api.workspace import GuestWorkspace, GuestWorkspaceStore
from app.domain.common import DomainModel
from app.domain.samples import available_samples, load_sample

COOKIE_NAME = "__Host-crickops_guest"


class CreateWorkspaceInput(DomainModel):
    sample_id: str | None = Field(default=None, max_length=80)


class ConfirmationInput(DomainModel):
    confirmation: bool


class WeatherRefreshInput(DomainModel):
    mode: Literal["live", "deterministic"] = "live"
    venue_ids: tuple[str, ...] = ()


class GenericPayload(DomainModel):
    payload: Mapping[str, Any] = {}


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
            workspace.tournament.model_dump(mode="json") if workspace.tournament else None
        ),
        "weather": workspace.weather,
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
    return workspace


def build_v1_router(store: GuestWorkspaceStore) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

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
    def create_workspace(body: CreateWorkspaceInput, response: Response) -> dict[str, object]:
        token, workspace = store.create(_load_requested_sample(body.sample_id))
        response.set_cookie(
            COOKIE_NAME,
            token,
            secure=True,
            httponly=True,
            samesite="lax",
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
        return {"status": "deletion_accepted"}

    @router.post("/workspace/reset")
    def reset_workspace(
        body: CreateWorkspaceInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        workspace.tournament = _load_requested_sample(body.sample_id)
        workspace.weather = {
            "mode": "live",
            "quality": "not_requested",
            "demo_mode_available": True,
            "scenario_id": None,
        }
        return _workspace_view(workspace)

    @router.get("/workspace/export")
    def export_workspace(
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        return JSONResponse(
            content=_workspace_view(workspace),
            headers={"Content-Disposition": "attachment; filename=crickops-tournament.json"},
        )

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
        return workspace.tournament

    @router.put("/tournament")
    def replace_tournament(
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        from app.domain.tournament import TournamentConfig

        workspace.tournament = TournamentConfig.model_validate(body)
        return workspace.tournament

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
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        del workspace
        return {"status": "confirmed", "selection": body}

    @router.post("/constraints/reject")
    def reject_constraints(
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        del workspace
        return {"status": "rejected", "selection": body}

    @router.post("/tournament/precheck")
    def precheck_tournament(
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        del body
        return {
            "ready": workspace.tournament is not None,
            "violations": [] if workspace.tournament else ["tournament_missing"],
        }

    @router.post("/weather/refresh")
    def refresh_weather(
        body: WeatherRefreshInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        workspace.weather = {
            "mode": body.mode,
            "quality": "unavailable" if body.mode == "live" else "deterministic",
            "demo_mode_available": True,
            "scenario_id": None,
            "guidance": "Weather risk is planning guidance only.",
        }
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
        workspace.weather = {
            "mode": "deterministic",
            "quality": "complete",
            "demo_mode_available": True,
            "scenario_id": scenario_id,
            "guidance": "Weather risk is planning guidance only.",
        }
        return workspace.weather

    @router.post("/weather/thresholds")
    def propose_weather_threshold(
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        del workspace
        return {"status": "proposed", "classification": "hard", "threshold": body}

    return router
