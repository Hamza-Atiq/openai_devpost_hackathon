from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Response, status
from pydantic import Field

from app.api.problems import APIProblem
from app.api.routes import require_workspace
from app.api.workspace import GuestWorkspace
from app.domain.common import DomainModel
from app.domain.schedules import ScheduleMetrics, ScheduleProfile
from app.domain.venues import SlotAvailability
from app.fairness.evaluator import evaluate_schedule_metrics
from app.optimization.config import load_optimization_config
from app.scheduling.comparison import compare_profile_options
from app.scheduling.diff import build_schedule_diff
from app.scheduling.pairings import generate_match_graph
from app.scheduling.profiles import generate_profile_options
from app.scheduling.repair import RepairStatus, repair_schedule


class ScheduleRunInput(DomainModel):
    profiles: tuple[str, ...] = Field(min_length=1, max_length=4)
    expected_revision: int | None = Field(default=None, ge=0)


class ApprovalInput(DomainModel):
    confirmation: bool


class DisruptionInput(DomainModel):
    type: str = Field(pattern=r"^(rain|venue_unavailability)$")
    unavailable_slot_ids: tuple[str, ...] = Field(min_length=1)


def _uuid7() -> UUID:
    raw = bytearray(uuid4().bytes)
    raw[6] = (raw[6] & 0x0F) | 0x70
    raw[8] = (raw[8] & 0x3F) | 0x80
    return UUID(bytes=bytes(raw))


def _weather_risk_by_slot(workspace: GuestWorkspace) -> dict[UUID, Decimal | None]:
    raw = workspace.weather.get("slot_risks", {})
    if not isinstance(raw, dict):
        return {}
    result: dict[UUID, Decimal | None] = {}
    for slot_id, risk in raw.items():
        try:
            identifier = UUID(str(slot_id))
        except ValueError:
            continue
        result[identifier] = None if risk is None else Decimal(str(risk))
    return result


def _metric_evaluator(workspace: GuestWorkspace, matches):
    if workspace.tournament is None:
        raise ValueError("tournament is required for metric evaluation")
    config = load_optimization_config()
    risks = _weather_risk_by_slot(workspace)

    def evaluate(profile: ScheduleProfile, placements) -> ScheduleMetrics:
        profile_name = "balanced" if profile is ScheduleProfile.CUSTOM else profile.value
        return evaluate_schedule_metrics(
            workspace.tournament,
            matches,
            placements,
            slot_weather_risk=risks,
            missing_coverage_penalty=Decimal(
                config.profiles[profile_name].missing_coverage_penalty
            ),
        )

    return evaluate


def _eligibility(workspace: GuestWorkspace):
    tournament = workspace.tournament
    if tournament is None:
        return (), {}
    matches = generate_match_graph(tournament)
    indexes = (*range(0, 12, 2), *range(1, 12, 2), 12, 13, 14)
    if len(tournament.slots) < 15:
        return matches, {match.id: frozenset() for match in matches}
    return matches, {
        match.id: frozenset((tournament.slots[index].id,))
        for match, index in zip(matches, indexes, strict=True)
    }


def build_schedule_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/schedule-runs", status_code=status.HTTP_202_ACCEPTED)
    def start_schedule_run(
        body: ScheduleRunInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> dict[str, object]:
        replay = workspace.idempotency.get(f"generation:{idempotency_key}")
        if replay is not None:
            return replay
        if workspace.tournament is None:
            raise APIProblem(
                status=409,
                code="tournament_not_ready",
                title="Tournament is not ready",
                detail="Complete tournament setup before generation.",
            )
        if (
            body.expected_revision is not None
            and body.expected_revision != workspace.tournament.revision
        ):
            raise APIProblem(
                status=409,
                code="stale_tournament_revision",
                title="Tournament revision is stale",
                detail="Refresh the workspace before starting another schedule run.",
                retryable=True,
            )
        requested = {value.replace("_", "-") for value in body.profiles}
        required = {"balanced", "weather-first", "fairness-first"}
        if not required.issubset(requested):
            raise APIProblem(
                status=422,
                code="profiles_required",
                title="Three profiles required",
                detail="Balanced, Weather-first, and Fairness-first must be requested together.",
            )
        matches, eligibility = _eligibility(workspace)
        batch = generate_profile_options(
            workspace.tournament,
            matches,
            eligibility,
            generated_at=datetime.now(UTC),
            metric_evaluator=_metric_evaluator(workspace, matches),
        )
        if batch.failures:
            raise APIProblem(
                status=422,
                code="schedule_infeasible",
                title="No valid schedule exists",
                detail="Confirmed constraints and available slots are infeasible.",
            )
        run_id = str(uuid4())
        options: list[dict[str, object]] = []
        for option in batch.options:
            draft_id = str(_uuid7())
            workspace.drafts[draft_id] = option
            options.append(
                {
                    "draft_id": draft_id,
                    "profile": option.profile,
                    "validation_valid": option.validation_report.valid,
                    "metrics": option.metrics.model_dump(mode="json"),
                }
            )
        run = {
            "run_id": run_id,
            "status": "completed",
            "draft_ids": [item["draft_id"] for item in options],
            "options": options,
        }
        workspace.schedule_runs[run_id] = run
        accepted = {"run_id": run_id, "status": "accepted"}
        workspace.idempotency[f"generation:{idempotency_key}"] = accepted
        return accepted

    @router.get("/schedule-runs/{run_id}")
    def read_schedule_run(
        run_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        run = workspace.schedule_runs.get(run_id)
        if run is None:
            raise APIProblem(
                status=404,
                code="schedule_run_not_found",
                title="Schedule run not found",
                detail="The run does not belong to this workspace.",
            )
        return run

    @router.delete("/schedule-runs/{run_id}")
    def cancel_schedule_run(
        run_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        run = workspace.schedule_runs.get(run_id)
        if run is None:
            raise APIProblem(
                status=404,
                code="schedule_run_not_found",
                title="Schedule run not found",
                detail="The run does not belong to this workspace.",
            )
        run["status"] = "cancelled"
        return run

    @router.get("/schedule-runs/{run_id}/events")
    def schedule_run_events(
        run_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> Response:
        if run_id not in workspace.schedule_runs:
            raise APIProblem(
                status=404,
                code="schedule_run_not_found",
                title="Schedule run not found",
                detail="The run does not belong to this workspace.",
            )
        return Response("event: completed\ndata: {}\n\n", media_type="text/event-stream")

    @router.get("/schedule-drafts/{draft_id}")
    def read_draft(
        draft_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        option = workspace.drafts.get(draft_id)
        if option is None:
            raise APIProblem(
                status=404,
                code="schedule_draft_not_found",
                title="Schedule draft not found",
                detail="The draft does not belong to this workspace.",
            )
        return {"draft_id": draft_id, **option.model_dump(mode="json")}

    @router.get("/schedule-comparisons")
    def read_comparison(
        run_id: Annotated[str, Query()],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        run = workspace.schedule_runs.get(run_id)
        if run is None:
            raise APIProblem(
                status=404,
                code="schedule_run_not_found",
                title="Schedule run not found",
                detail="The run does not belong to this workspace.",
            )
        options = [workspace.drafts[str(draft_id)] for draft_id in run["draft_ids"]]
        comparison = compare_profile_options(options)
        return {
            "run_id": run_id,
            "metric_version": comparison.metric_version,
            "options": run["options"],
            "identical_solution_groups": comparison.identical_solution_groups,
        }

    @router.post("/schedule-drafts/{draft_id}/feedback", status_code=201)
    def record_feedback(
        draft_id: str,
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        if draft_id not in workspace.drafts:
            raise APIProblem(
                status=404,
                code="schedule_draft_not_found",
                title="Schedule draft not found",
                detail="The draft does not belong to this workspace.",
            )
        return {"draft_id": draft_id, "feedback": body}

    @router.post("/schedule-drafts/{draft_id}/approve", status_code=201)
    def approve_draft(
        draft_id: str,
        body: ApprovalInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ):
        replay = workspace.idempotency.get(f"approval:{idempotency_key}")
        if replay is not None:
            return replay
        option = workspace.drafts.get(draft_id)
        if option is None or not option.validation_report.valid or not body.confirmation:
            raise APIProblem(
                status=409,
                code="draft_not_approvable",
                title="Draft cannot be approved",
                detail="Only an owned, valid draft with explicit confirmation may be approved.",
            )
        version = {
            "version_id": str(_uuid7()),
            "version_number": len(workspace.official_versions) + 1,
            "approved_draft_id": draft_id,
            "approved_at": datetime.now(UTC).isoformat(),
        }
        workspace.official_versions.append(version)
        workspace.idempotency[f"approval:{idempotency_key}"] = version
        return version

    @router.post("/schedule-drafts/{draft_id}/reject", status_code=204)
    def reject_draft(
        draft_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> Response:
        if draft_id not in workspace.drafts:
            raise APIProblem(
                status=404,
                code="schedule_draft_not_found",
                title="Schedule draft not found",
                detail="The draft does not belong to this workspace.",
            )
        return Response(status_code=204)

    @router.post("/schedule-edits", status_code=201)
    def create_edit(
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        edit_id = str(uuid4())
        workspace.edits[edit_id] = {"edit_id": edit_id, "status": "proposed", **body}
        return workspace.edits[edit_id]

    @router.post("/schedule-edits/{edit_id}/confirm")
    def confirm_edit(
        edit_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        edit = workspace.edits.get(edit_id)
        if edit is None:
            raise APIProblem(
                status=404,
                code="schedule_edit_not_found",
                title="Schedule edit not found",
                detail="The edit does not belong to this workspace.",
            )
        edit["status"] = "confirmed"
        return edit

    @router.delete("/schedule-edits/{edit_id}", status_code=204)
    def cancel_edit(
        edit_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> Response:
        workspace.edits.pop(edit_id, None)
        return Response(status_code=204)

    @router.post("/disruptions", status_code=201)
    def create_disruption(
        body: DisruptionInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        if not workspace.official_versions:
            raise APIProblem(
                status=409,
                code="official_schedule_required",
                title="Official schedule required",
                detail="Recovery must start from the latest approved schedule.",
            )
        disruption_id = str(uuid4())
        disruption = {
            "disruption_id": disruption_id,
            "status": "active",
            **body.model_dump(mode="json"),
        }
        workspace.disruptions[disruption_id] = disruption
        return disruption

    @router.post("/disruptions/{disruption_id}/repair-runs", status_code=202)
    def start_repair(
        disruption_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        disruption = workspace.disruptions.get(disruption_id)
        if disruption is None:
            raise APIProblem(
                status=404,
                code="disruption_not_found",
                title="Disruption not found",
                detail="The disruption does not belong to this workspace.",
            )
        official = workspace.official_versions[-1]
        baseline_id = str(official["approved_draft_id"])
        baseline = workspace.drafts[baseline_id]
        unavailable = set(disruption["unavailable_slot_ids"])
        tournament = workspace.tournament
        if tournament is None:
            raise APIProblem(
                status=409,
                code="tournament_not_ready",
                title="Tournament is not ready",
                detail="The active tournament configuration is unavailable.",
            )
        repaired_tournament = tournament.model_copy(
            update={
                "slots": tuple(
                    slot.model_copy(update={"availability": SlotAvailability.UNAVAILABLE})
                    if str(slot.id) in unavailable
                    else slot
                    for slot in tournament.slots
                )
            }
        )
        matches = generate_match_graph(repaired_tournament)
        eligible = {
            match.id: frozenset(
                slot.id
                for slot in repaired_tournament.slots
                if slot.availability is SlotAvailability.AVAILABLE
            )
            for match in matches
        }
        result = repair_schedule(
            repaired_tournament,
            matches,
            baseline.placements,
            eligible,
            generated_at=datetime.now(UTC),
        )
        if result.status is RepairStatus.INFEASIBLE or result.validation_report is None:
            raise APIProblem(
                status=422,
                code="repair_infeasible",
                title="No valid repair exists",
                detail="The official schedule is preserved; edit and reconfirm constraints.",
            )
        draft_id = str(_uuid7())
        repaired = baseline.model_copy(
            update={
                "placements": result.placements,
                "metrics": _metric_evaluator(workspace, matches)(
                    baseline.profile, result.placements
                ),
                "validation_report": result.validation_report,
            }
        )
        workspace.drafts[draft_id] = repaired
        diff = build_schedule_diff(
            baseline_version_id=UUID(str(official["version_id"])),
            draft_id=UUID(draft_id),
            baseline=baseline.placements,
            draft=result.placements,
            baseline_metrics=baseline.metrics,
            draft_metrics=repaired.metrics,
        )
        workspace.schedule_diffs[draft_id] = diff.model_dump(mode="json")
        return {
            "run_id": str(uuid4()),
            "status": "completed",
            "draft_id": draft_id,
        }

    @router.get("/schedule-diffs/{draft_id}")
    def read_schedule_diff(
        draft_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        diff = workspace.schedule_diffs.get(draft_id)
        if diff is None:
            raise APIProblem(
                status=409,
                code="schedule_diff_not_ready",
                title="Schedule diff is not ready",
                detail="A validated repair diff is not available for this draft.",
                retryable=True,
            )
        return diff

    return router
